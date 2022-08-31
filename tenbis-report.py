import requests
import os.path
import pickle
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TENBIS_FQDN="https://www.10bis.co.il"
DEBUG=False

def main_procedure():
    sessionpicklepath = '/var/tmp/sessions.pickle'
    session = ''
    if (os.path.exists(sessionpicklepath) and os.path.exists('/var/tmp/usertoken.pickle')):
        session = loadpickle(sessionpicklepath)
        usertoken = loadpickle('/var/tmp/usertoken.pickle')
        session.usertoken = usertoken
    else:
        session=auth_tenbis()
        createpickle(session,sessionpicklepath)
    
    htmlversion = """
        <html>
        <head> <title></title> </head>
        <body>
            <table border=1>
            <tr> <td>Item number</td>  <td>Order date</td>   <td>Barcode number</td>   <td>Barcode image</td>   <td>Amount</td>   <td>Expiration date</td>
            xxxdataxxx
            </table>
        </body>
        </html>
    """

    rowsdata=''
    rowtemplate = """
    <tr>  <td>xxxcountxxx</td>   <td>xxxorderDateStrxxx</td>   <td>xxxBarCodeNumberxxx</td>   <td><img src='xxxBarCodeImgUrlxxx'></td>   <td>xxxAmountxxx</td>   <td>xxxValidDatexxx</td></tr>
    <tr> <td></td>   <td></td>   <td></br></br></br></td>   <td></td>   <td></td></tr>
    """
    count = 0
    for num in range(0, 38):
        monthstr = '-xxxnumxxx'
        if num == 0:
            monthstr = 'xxxnumxxx'
        monthstr = monthstr.replace('xxxnumxxx',str(num))
        jsonresultsformonth = get_report_for_month(session,monthstr)
        for order in jsonresultsformonth:
            #print(order)
            used, BarCodeNumber, BarCodeImgUrl, Amount, ValidDate = getShufersalOrderInfo(session, order['orderId'], order['restaurantId'])
            if not used:
                count+=1
                newrow = rowtemplate
                newrow = newrow.replace('xxxcountxxx',str(count))
                newrow = newrow.replace('xxxorderDateStrxxx',order['orderDateStr'])
                newrow = newrow.replace('xxxBarCodeNumberxxx',BarCodeNumber)
                newrow = newrow.replace('xxxBarCodeImgUrlxxx',BarCodeImgUrl)
                newrow = newrow.replace('xxxAmountxxx',Amount)
                newrow = newrow.replace('xxxValidDatexxx', ValidDate)
                rowsdata += newrow
                print("Token found! ", order['orderDateStr'], BarCodeNumber, BarCodeImgUrl, Amount, ValidDate)
    htmlversion = htmlversion.replace('xxxdataxxx',rowsdata)
    if count > 0:
        with open('/var/tmp/report.html', 'a') as report_file:
            report_file.write(htmlversion)
            report_file.close()
        print(str(count), "tokens were found!")
        print('Please find your report here: /var/tmp/report.html')



def createpickle(obj, path):
    with open(path, 'wb') as session_file:
        pickle.dump(obj, session_file)

def loadpickle(path):
    with open(path, 'rb') as session_file:
        objfrompickle = pickle.load(session_file)
        return objfrompickle

def get_report_for_month(session,month):
    endpoint = "/NextApi/UserTransactionsReport"
    endpoint = TENBIS_FQDN+endpoint
    payload = """{"culture":"he-IL","uiCulture":"he","dateBias":"xxxmonthsbackxxx"}"""
    payload = payload.replace("xxxmonthsbackxxx",month)
    headers = { 'content-type': "application/json" }
    headers.update({'user-token': session.usertoken})
    response = session.post(endpoint, data=payload, headers=headers, verify=False)
    if(DEBUG):
        print(endpoint + "\r\n" + str(response.status_code) + "\r\n"  + response.text)
    respjson = json.loads(response.text)
    all_orders = respjson['Data']['orderList']
    shufersal_orders = [x for x in all_orders if x['isBarCodeOrder'] == True]
    return shufersal_orders

def getShufersalOrderInfo(session, orderid,resid):
    endpoint = "/NextApi/GetOrderBarcode?culture=he-IL&uiCulture=he&orderId=xxxorderidxxx&resId=xxxresidxxx"
    endpoint = endpoint.replace("xxxorderidxxx",str(orderid))
    endpoint = endpoint.replace("xxxresidxxx",str(resid))
    endpoint = TENBIS_FQDN+endpoint
    headers = { 'content-type': "application/json" }
    headers.update({'user-token': session.usertoken})
    response = session.get(endpoint, headers=headers, verify=False)
    respjson = json.loads(response.text)
    used = respjson['Data']['Vouchers'][0]['Used']
    if used:
        return used, '', '', '', ''
    else:
        BarCodeNumber = respjson['Data']['Vouchers'][0]['BarCodeNumber']
        BarCodeImgUrl = respjson['Data']['Vouchers'][0]['BarCodeImgUrl']
        Amount = respjson['Data']['Vouchers'][0]['Amount']
        ValidDate = respjson['Data']['Vouchers'][0]['ValidDate']
        return used, BarCodeNumber, BarCodeImgUrl, Amount, ValidDate

def auth_tenbis():
    u = input("Enter email: ")
    endpoint = "/NextApi/GetUserAuthenticationDataAndSendAuthenticationCodeToUser"
    endpoint = TENBIS_FQDN+endpoint
    payload = """
        {"culture":"he-IL","uiCulture":"he","email":"xxxemailxxx"}
    """
    payload = payload.replace("xxxemailxxx",u)
    headers = { 'content-type': "application/json" }
    session = requests.session()
    response = session.post(endpoint, data=payload, headers=headers, verify=False)
    respjson = json.loads(response.text)
    if(DEBUG):
            print(endpoint + "\r\n" + str(response.status_code) + "\r\n"  + response.text)
    if (200 <= response.status_code <= 210):
        print("login successful")
    else:
        print("login failed")
    

    # phase two - OTP
    endpoint = "/NextApi/GetUserV2"
    endpoint = TENBIS_FQDN+endpoint
    auth_token =  respjson['Data']['codeAuthenticationData']['authenticationToken']
    shop_cart_guid = respjson['ShoppingCartGuid']

    otp = input("Enter OTP: ")
    payload = """
    {"shoppingCartGuid":"xxxshopcartguidxxx","culture":"he-IL","uiCulture":"he","email":"xxxemailxxx","authenticationToken":"xxxauthtokenxxx","authenticationCode":"xxxotpxxx"}
    """
    payload = payload.replace("xxxauthtokenxxx",auth_token)
    payload = payload.replace("xxxemailxxx",u)
    payload = payload.replace("xxxshopcartguidxxx",shop_cart_guid)
    payload = payload.replace("xxxotpxxx",otp)
    response = session.post(endpoint, data=payload, headers=headers, verify=False)
    respjson = json.loads(response.text)
    usertoken=respjson['Data']['userToken']
    createpickle(usertoken,'/var/tmp/usertoken.pickle')
    session.usertoken = usertoken
    if(DEBUG):
        print(endpoint + "\r\n" + str(response.status_code) + "\r\n"  + response.text)
        print(session)
    return session



main_procedure()
