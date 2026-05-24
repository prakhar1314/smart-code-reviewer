import requests, json, time

def get_data(url, retries):
    for i in range(retries):
        try:
            r = requests.get(url)
            data = json.loads(r.text)
            return data
        except:
            time.sleep(2)
    return None

def process(data):
    result = []
    for d in data:
        if d['status'] == 1:
            if d['amount'] > 100:
                if d['country'] == 'US' or d['country'] == 'CA' or d['country'] == 'UK':
                    result.append({'id': d['id'], 'total': d['amount'] * 1.1})
    return result

def main():
    d = get_data("http://api.example.com/orders", 3)
    r = process(d)
    print(r)

main()
