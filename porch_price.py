#!/usr/bin/env python3
import requests
import re
import json
import time
import datetime
import mongoengine
import credentials
from models import CostLink, ZipCode, Price
from data import machine_name
import sys
import threading

def get_price_content(session, url_slug, apply_zip_codes, csrf_token):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:83.0) Gecko/20100101 Firefox/83.0',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json',
            'Origin': 'https://porch.com',
            'Connection': 'keep-alive',
            'Referer': 'https://porch.com/project-cost/' + url_slug,
            'TE': 'Trailers',
        }

        i = 0
        for code in apply_zip_codes:
            i = i + 1
            data = {
                "requests": {
                    "g0": {
                        "resource": "costCalculator",
                        "operation": "read",
                        "params": {
                            "includeCompanies": True,
                            "includeDetails": True,
                            "skipLoad": False,
                            "calculatorType": "" + url_slug,
                            "postalCode": code,
                            "unitTotal": 1,
                            "userInput": True
                        }
                    }
                }, "context": {
                    "lang": "en-US",
                    "_csrf": csrf_token
                }
            }

            response = session.post(
                'https://porch.com/api-frontend-cost-calculator/?_csrf={}&lang=en-US'.format(csrf_token),
                headers=headers,
                data=json.dumps(data),
                # proxies=proxies
            )
            print(i, code)
            item = json.loads(response.text)
            item_data = item['g0']['data']
            del item_data['similarCalculatorsDTO']
            del item_data['relatedAdvice']
            del item_data['topPopularCalculatorsDTO']
            del item_data['topRelatedServicesCalculatorsDTO']
            del item_data['topSameServiceCalculatorsDTO']
            del item_data['relatedProjectDTO']
            del item_data['selectedProDTOs']
            del item_data['calculatorFaqDTOs']
            content = json.dumps(item_data)
            Price.objects(zipcode=code, url_slug=url_slug).update_one(set__content=content, set__blank=False, upsert=True)
            time.sleep(1)
    except Exception as ex:
        print("*********Error*************")
        print(ex)
        pass

def start_scrape(url_slug):
    try:
        prices = Price.objects.filter(url_slug=url_slug, blank=True).limit(1500)
        if prices.count() == 0:
            CostLink.objects(url_slug=url_slug).update_one(status='Done', upsert=True)
            return
        CostLink.objects(url_slug=url_slug).update_one(status='In-Progress', upsert=True)
        apply_zip_codes = list(map(lambda x: x.zipcode, prices))
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:83.0) Gecko/20100101 Firefox/83.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://porch.com/project-cost',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'TE': 'Trailers',
        }

        # proxies = {
        #     'http': 'http://195.25.19.4:3128',
        #     'https': 'http://195.25.19.4:3128'
        # }

        session = requests.Session()
        print("Waiting Response ...")
        response = session.get(
            'https://porch.com/project-cost/' + url_slug,
            headers=headers,
            # proxies=proxies
        )

        regex = re.search(
            r'"CsrfStore":\{"token":"(.*?)"\}',
            response.text,
            re.S | re.M | re.I
        )
        csrf_token = regex.group(1)

        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:83.0) Gecko/20100101 Firefox/83.0',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json',
            'Origin': 'https://porch.com',
            'Connection': 'keep-alive',
            'Referer': 'https://porch.com/project-cost/' + url_slug,
            'TE': 'Trailers',
        }

        print("Token : ", csrf_token)
        
        # first_index = len(apply_zip_codes) // 3
        # second_index = first_index * 2
        
        # first_list = apply_zip_codes[:first_index]
        # second_list = apply_zip_codes[first_index:second_index]
        # third_list = apply_zip_codes[second_index:]
        
        for codes in [apply_zip_codes]:
            threads = list()
            print("Main    : create and start thread {}.".format(len(codes)))
            x = threading.Thread(target=get_price_content, args=(session, url_slug, codes, csrf_token))
            threads.append(x)
            time.sleep(1)
            x.start()

        for index, thread in enumerate(threads):
            print("Main    : before joining thread {}.".format(index))
            thread.join()
            print("Main    : thread {} done".format(index))
    except Exception as ex:
        print("*********Error*************")
        print(ex)
    
if __name__ == "__main__":  

    # TODO
    # 1. Connect Remote DB
    # 2. Supervisor to continue run

    # mongoengine.connect(
    #     db=credentials.DB_DATABASE, host=credentials.DB_HOST,
    #     username=credentials.DB_USER, password=credentials.DB_PASSWORD, port=credentials.DB_PORT)    
    mongoengine.connect(host=credentials.DB_URI)

    cost_links = CostLink.objects.filter(machine = machine_name, status__ne='Done')

    for cost_link in cost_links:
        print("***********Start************")
        print(cost_link.url_slug, datetime.datetime.now())
        start_scrape(cost_link.url_slug)
        prices = Price.objects.filter(url_slug=cost_link.url_slug, blank=True).count()
        if prices:
            cost_link.status = 'In-Progress'
            cost_link.save()
            break
        else:
            cost_link.status = 'Done'
            cost_link.save()

        time.sleep(30)
        print(cost_link.url_slug, datetime.datetime.now())
        print("*****************Done*******************")
