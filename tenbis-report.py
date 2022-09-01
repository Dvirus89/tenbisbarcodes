import requests
import os.path
import pickle
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SESSION_PATH = "/var/tmp/sessions.pickle"
TOKEN_PATH = "/var/tmp/usertoken.pickle"
OUTPUT_PATH = "/var/tmp/report.html"
TENBIS_FQDN = "https://www.10bis.co.il"
DEBUG = False
HTML_ROW_TEMPLATE = """
    <tr>  <td>{counter}</td>   <td>{order_date}</td>   <td>{barcode_number}</td>   <td><img src='{barcode_img_url}'></td>   <td>{amount}</td>   <td>{valid_date}</td></tr>
    <tr> <td></td>   <td></td>   <td></br></br></br></td>   <td></td>   <td></td></tr>
    """
HTML_PAGE_TEMPLATE = """
        <html>
        <head> <title></title> </head>
        <body>
            <table border=1>
            <tr> <td>Item number</td>  <td>Order date</td>   <td>Barcode number</td>   <td>Barcode image</td>   <td>Amount</td>   <td>Expiration date</td>
            {output_table}
            </table>
        </body>
        </html>
    """

def main_procedure():
    # If token exists, use the token to authenticate 10bis
    if os.path.exists(SESSION_PATH) and os.path.exists(TOKEN_PATH):
        session = load_pickle(SESSION_PATH)
        user_token = load_pickle(TOKEN_PATH)
        session.user_token = user_token

    # If there's no token, authenticate 10bis and extract auth tokens
    else:
        session = auth_tenbis()
        create_pickle(session,SESSION_PATH)

    rows_data=''
    count = 0
    for num in range(0, -38, -1):
        month_json_result = get_report_for_month(session, str(num))
        for order in month_json_result:
            used, barcode_number, barcode_img_url, amount, valid_date = get_shufersal_order_info(session, order['orderId'], order['restaurantId'])
            if not used:
                count+=1
                rows_data += HTML_ROW_TEMPLATE.format(counter=str(count), order_date=order['orderDateStr'], barcode_number=barcode_number,
                                                    barcode_img_url=barcode_img_url, amount=amount, valid_date=valid_date)
                print("Token found! ", order['orderDateStr'], barcode_number, barcode_img_url, amount, valid_date)

    if count > 0:
        write_file(OUTPUT_PATH, HTML_PAGE_TEMPLATE.format(output_table=rows_data))
        print(str(count), "tokens were found!")
        print(f'Please find your report here: {OUTPUT_PATH}')


def write_file(path, content):
    with open(path, 'w') as f:
        f.write(content)


def create_pickle(obj, path):
    with open(path, 'wb') as session_file:
        pickle.dump(obj, session_file)

def load_pickle(path):
    with open(path, 'rb') as session_file:
        objfrompickle = pickle.load(session_file)
        return objfrompickle

def get_report_for_month(session, month):
    endpoint = TENBIS_FQDN + "/NextApi/UserTransactionsReport"
    payload = {"culture": "he-IL", "uiCulture": "he", "dateBias": month}
    headers = {"content-type": "application/json", "user-token": session.user_token}
    response = session.post(endpoint, data=json.dumps(payload), headers=headers, verify=False)

    if(DEBUG):
        print(endpoint + "\r\n" + str(response.status_code) + "\r\n"  + response.text)

    resp_json = json.loads(response.text)
    all_orders = resp_json['Data']['orderList']
    shufersal_orders = [x for x in all_orders if x['isBarCodeOrder'] == True]
    
    return shufersal_orders

def get_shufersal_order_info(session, order_id, res_id):
    endpoint = TENBIS_FQDN + f"/NextApi/GetOrderBarcode?culture=he-IL&uiCulture=he&orderId={order_id}&resId={res_id}"
    headers = {"content-type": "application/json"}
    headers.update({'user-token': session.user_token})
    response = session.get(endpoint, headers=headers, verify=False)
    resp_json = json.loads(response.text)
    used = resp_json['Data']['Vouchers'][0]['Used']

    if not used:
        barcode_number = resp_json['Data']['Vouchers'][0]['BarCodeNumber']
        barcode_img_url = resp_json['Data']['Vouchers'][0]['BarCodeImgUrl']
        amount = resp_json['Data']['Vouchers'][0]['Amount']
        valid_date = resp_json['Data']['Vouchers'][0]['ValidDate']
        return used, barcode_number, barcode_img_url, amount, valid_date

    return used, '', '', '', ''

# Test this
def auth_tenbis():
    # Phase one -> Email
    email = input("Enter email: ")
    endpoint = TENBIS_FQDN + "/NextApi/GetUserAuthenticationDataAndSendAuthenticationCodeToUser"

    payload = {"culture": "he-IL", "uiCulture": "he", "email": email}
    headers = {"content-type": "application/json"}
    session = requests.session()

    response = session.post(endpoint, data=json.dumps(payload), headers=headers, verify=False)
    resp_json = json.loads(response.text)

    if(DEBUG):
        print(endpoint + "\r\n" + str(response.status_code) + "\r\n"  + response.text)

    if (200 <= response.status_code <= 210):
        print("login successful")
    else:
        print("login failed")

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
    user_token = resp_json['Data']['userToken']

    create_pickle(user_token, TOKEN_PATH)
    session.user_token = user_token

    if(DEBUG):
        print(endpoint + "\r\n" + str(response.status_code) + "\r\n"  + response.text)
        print(session)

    return session


if __name__ == '__main__':
    main_procedure()
