import requests
import os
import urllib3
import json
from datetime import date


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
CWD=os.getcwd()
FILENAME = f"report-{date.today().strftime('%d-%b-%Y')}.html"
OUTPUT_PATH = f"{CWD}/{FILENAME}"
TENBIS_FQDN = "https://www.10bis.co.il"
TENBIS_API_FQDN = "https://api.10bis.co.il"
DEBUG = False

# Restaurant IDs to scan (26698 is Shufersal, 42962 is Victory)
RESTAURANTS = [26698, 42962]

HTML_ROW_TEMPLATE = """
    <tr>  <td>{counter}</td>  <td>{store}</td>   <td>{order_date}</td>   <td>{barcode_number}</td>   <td style="text-align:center;"><img onclick="togglehideshow(this)" src='{barcode_img_url}'></td>   <td>{amount}</td>   <td>{valid_date}</br></br></td></tr>
    """
HTML_PAGE_TEMPLATE = """
        <!DOCTYPE html>
        <html>
        <head>
        <script>
            function togglehideshow(element) {{
                 element.style.opacity= element.style.opacity * -1; 
            }}
            
            function hideall() {{
                var elems = document.getElementsByTagName('img');
                for (var i = 0; i < elems.length; i++) {{
                    elems[i].style.opacity = -1;
                }}
            }}
            
            function showall() {{
                var elems = document.getElementsByTagName('img');
                for (var i = 0; i < elems.length; i++) {{
                    elems[i].style.opacity = 1;
                }}
            }}
            
        </script>
        <style>
        button {{
        background-color: #43b17d; /* Green */
        border: none;
        padding: 20px;
        width: 48%;
        margin: 1%;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        cursor: pointer;
        border-radius: 12px;
        }}
        #barcodes {{
        font-family: Arial, Helvetica, sans-serif;
        border-collapse: collapse;
        width: 100%;
        }}
        
        img {{
        opacity: 1;
        max-width: 300px;
        }}

        #barcodes td, #barcodes th {{
        border: 1px solid #ddd;
        padding: 8px;
        }}

        #barcodes tr:nth-child(even){{
        background-color: #f2f2f2;}}

        #barcodes tr:hover {{background-color: #ddd;}}

        #barcodes th {{
        padding-top: 12px;
        padding-bottom: 12px;
        vertical-align: top;
        text-align: center;
        background-color: #04AA6D;
        color: white;
        }}
        </style>
        </head>
        <body>
            <h1> Non used barcodes </h1>
            <table id="barcodes">
            <tr> <th>Item number</th> <th>Store</th>  <th>Order date</th>   <th>Barcode number</th>   <th>Barcode image</br><button onclick="showall()">Show all</button><button onclick="hideall()">Hide all</button></th>   <th>Amount</th>   <th>Expiration date</th>
            {output_table}
            </table>
        </body>
        </html>
    """

def main_procedure():
    # Always authenticate fresh since pickle is removed
    session = auth_tenbis()
    if(not session):
        print("exit")
        return

    rows_data=''
    count = 0
    total_amount = 0
    
    print(f"Scanning for vouchers in restaurants: {RESTAURANTS}...")

    for res_id in RESTAURANTS:
        # 1. Get all valid vouchers from the new API
        vouchers_list = get_user_vouchers(session, res_id)
        
        for order in vouchers_list:
             # 2. Extract basic info from new API
            order_id = order.get('orderId')
            
            if DEBUG:
                print(f"Processing Order ID: {order_id}")

            # 3. Call OLD API to get the image URL and formatted barcode number
            used, barcode_number, barcode_img_url, amount, valid_date = get_barcode_order_info(session, order_id, res_id)
            
            # Fallback if old API fails to parse dates/amounts, use new API data
            if not amount: amount = order.get('amount')
            if not valid_date: valid_date = order.get('validTill')

            rows_data += HTML_ROW_TEMPLATE.format(counter=str(count), store=str(res_id), order_date=order.get('orderDate'), barcode_number=barcode_number,
                                                    barcode_img_url=barcode_img_url, amount=amount, valid_date=valid_date)
            count+=1
            total_amount += int(amount) if amount else 0
            print("Token found! ", count, order.get('orderDate'), barcode_number, amount)

    if count > 0:
        write_file(OUTPUT_PATH, HTML_PAGE_TEMPLATE.format(output_table=rows_data))
        print(f"{str(count)} tokens were found with total of {total_amount} NIS!")
        print(f'Please find your report here: {CWD} ({FILENAME})')
    else:
        print('No tokens were found.')

def get_user_vouchers(session, res_id):
    endpoint = f"{TENBIS_API_FQDN}/api/v1/VoucherCards/GetUserVouchers?restaurantId={res_id}"
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9",
        "user-token": session.user_token,
        "Authorization": f"Bearer {session.user_token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    response = session.get(endpoint, headers=headers, verify=False)
    
    if(DEBUG):
        print(endpoint + "\r\n" + str(response.status_code) + "\r\n"  + response.text)
        
    if response.status_code == 200:
        return json.loads(response.text)
    else:
        print(f"Failed to fetch vouchers for res_id {res_id}. Status: {response.status_code}")
        return []

def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def print_hebrew(heb_txt):
    print(heb_txt[::-1])

def get_barcode_order_info(session, order_id, res_id):
    endpoint = TENBIS_FQDN + f"/NextApi/GetOrderBarcode?culture=he-IL&uiCulture=he&orderId={order_id}&resId={res_id}"
    headers = {
        "content-type": "application/json",
        "user-token": session.user_token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
        "Referer": "https://www.10bis.co.il/"
    }
    response = session.get(endpoint, headers=headers, verify=False)
    if(DEBUG):
        print(endpoint + "\r\n" + str(response.status_code) + "\r\n"  + response.text)
    
    try:
        resp_json = json.loads(response.text)
        error_msg = resp_json.get('Error')
        success_code = resp_json.get('Success')
        
        if(not success_code):
             if error_msg: print_hebrew((error_msg.get('ErrorDesc', '')))
             return True, '', '', '', ''
             
        used = resp_json['Data']['Vouchers'][0]['Used']

        if not used:
            barcode_number = resp_json['Data']['Vouchers'][0]['BarCodeNumber']
            barcode_number_formatted = '-'.join(barcode_number[i:i+4] for i in range(0, len(barcode_number), 4))
            barcode_img_url = resp_json['Data']['Vouchers'][0]['BarCodeImgUrl']
            amount = resp_json['Data']['Vouchers'][0]['Amount']
            valid_date = resp_json['Data']['Vouchers'][0]['ValidDate']
            return used, barcode_number_formatted, barcode_img_url, amount, valid_date
    except Exception as e:
        if DEBUG: print(f"Error parsing detail for {order_id}: {e}")
        pass

    return True, '', '', '', ''

def auth_tenbis():
    # Phase one -> Email
    email = input("Enter email: ")
    endpoint = TENBIS_FQDN + "/NextApi/GetUserAuthenticationDataAndSendAuthenticationCodeToUser"

    payload = {"culture": "he-IL", "uiCulture": "he", "email": email}
    headers = {
        "content-type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
        "Referer": "https://www.10bis.co.il/"
    }
    session = requests.session()

    response = session.post(endpoint, data=json.dumps(payload), headers=headers, verify=False)
    if(DEBUG):
        print(endpoint + "\r\n" + str(response.status_code) + "\r\n"  + response.text)
    resp_json = json.loads(response.text)
    error_msg = resp_json['Errors']

    if (200 <= response.status_code <= 210 and (len(error_msg) == 0)):
        print("User exist, next step is...")
    else:
        print("login failed")
        print_hebrew((error_msg[0]['ErrorDesc']))
        return False

    # Phase two -> OTP
    endpoint = TENBIS_FQDN + "/NextApi/GetUserV2"
    auth_token =  resp_json['Data']['codeAuthenticationData']['authenticationToken']
    shop_cart_guid = resp_json['ShoppingCartGuid']

    otp = input("Enter OTP: ")
    payload = {"shoppingCartGuid": shop_cart_guid,
                "culture":"he-IL",
                "uiCulture":"he",
                "email": email,
                "authenticationToken": auth_token,
                "authenticationCode": otp}

    response = session.post(endpoint, data=json.dumps(payload), headers=headers, verify=False)
    resp_json = json.loads(response.text)
    error_msg = resp_json['Errors']
    user_token = resp_json['Data']['userToken']
    if (200 <= response.status_code <= 210 and (len(error_msg) == 0)):
        print("login successful...")
    else:
        print("login failed")
        print_hebrew((error_msg[0]['ErrorDesc']))
        return False

    session.user_token = user_token

    if(DEBUG):
        print(endpoint + "\r\n" + str(response.status_code) + "\r\n"  + response.text)
        print(session)

    return session

if __name__ == '__main__':
    main_procedure()
