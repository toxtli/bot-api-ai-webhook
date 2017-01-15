#!/usr/bin/env python

from apns import APNs, Frame, Payload
from tinydb import TinyDB, Query

import urllib2
import urllib
import random
import json
import sys
import os

from flask import Flask
from flask import request
from flask import make_response

# Flask app should start in global layout
app = Flask(__name__)
app.config['DEBUG'] = True

@app.route('/', methods=['GET','POST'])
def index():
    print("INDEX")
    res = '{"status":"YES"}'
    r = make_response(res)
    r.headers['Content-Type'] = 'application/json'
    return r

@app.route('/online', methods=['GET','POST'])
def online():
    print("ONLINE")
    params = request.args.to_dict()
    body = {"status": "INVALID", "code":""}
    if 'token' in params:
        body['status'] = 'OK'
        token = params['token']
        db = TinyDB('db.json')
        User = Query()
        users = db.search(User.token == token)
        if users:
            user = users[0]
            if user['code']:
                body['code'] = user['code']
        else:
            body['code'] = generate_code(token)
    exit = {"statusCode": "200", "headers": {}, "body": json.dumps(body)}
    res = json.dumps(exit)
    r = make_response(res)
    r.headers['Content-Type'] = 'application/json'
    return r

@app.route('/webhook', methods=['POST'])
def webhook():
    print("MSG RECEIVED")
    req = request.get_json(silent=True, force=True)
    print("Request:")
    print(json.dumps(req, indent=4))
    
    inputData = {
        "inputSource": req['originalRequest']['source'],
        "userId": req['originalRequest']['data']['user']['user_id'],
        "action": req['result']['action'],
        "parameters": req['result']['parameters'],
        "incomplete": req['result']['actionIncomplete'],
        "response": req['result']['fulfillment']['speech'],
        "input": req['result']['resolvedQuery']
    }
    print(json.dumps(inputData, indent=4))
    
    actionParts = inputData['action'].split('.')
    res = inputData['response']
    if actionParts[0] == 'self':
        res = evaluate(actionParts[1], inputData)
    print(res)
    
    r = make_response(res)
    r.headers['Content-Type'] = 'application/json'
    return r

def get_user_info(userId):
    user = None
    db = TinyDB('db.json')
    User = Query()
    users = db.search(User.userId == userId)
    if users:
        user = users[0]
    return user

def update_user(userId, code):
    db = TinyDB('db.json')
    User = Query()
    db.update({'code': '', 'userId': userId}, User.code == code)
    
def get_confirmation_code(userId, code):
    res = ''
    db = TinyDB('db.json')
    User = Query()
    users = db.search(User.code == code)
    if users:
        update_user(userId, code)
    else:
        res = "Your confirmation code is incorrect, " \
            "please provide me the confirmation code again, " \
            "by saying, The confirmation code is, and followed by " \
            " the number"
    return res

def get_random_number():
    return ''.join(["%s" % random.randint(0, 9) for num in range(0, 4)])

def generate_code(token):
    db = TinyDB('db.json')
    User = Query()
    while True:
        code = get_random_number()
        codes = db.search(User.code == code)
        if not codes:
            break
    db.insert({'token':token,'code':code,'userId':''})
    return code

def evaluate(method, data):
    message = data['response']
    userId = data['userId']
    user = get_user_info(userId)
    if method == 'welcome':
        if not user:
            message = "Welcome, I can see that you are a new user. In order to " \
                "be able to work with you, you need to install a Mac OS App, " \
                "if you have already installed it please provide me the " \
                "confirmation code by saying, The confirmation code is, " \
                "and followed by the separated four numbers"
    elif method == 'execute':
        if not user:
            message = "You received a confirmation code when the Mac OS " \
                "application was intalled, please provide me the " \
                "confirmation code by saying, The confirmation code is, " \
                "and followed by the separated four numbers"
        else:
            action = data['parameters']['Color']
            token = user['token']
            send_message(action, token)
    elif method == 'confirmation':
        code = data['parameters']['Code']
        hasErrors = get_confirmation_code(userId, code)
        if hasErrors:
            message = hasErrors
    res = responseFormat(message)
    res = json.dumps(res, indent=4)
    return res

def send_message(message, token):
    apns = APNs(use_sandbox=True, cert_file='aps_dev_cert.pem', key_file='aps_dev_key_decrypted.pem')
    payload = Payload(alert=message, sound="default", badge=1)
    apns.gateway_server.send_notification(token, payload)
    
def responseFormat(message):
    return {
        "speech": message,
        "displayText": message,
        "source": "apiai-weather-webhook-sample"
    }

def processRequest(req):
    if req.get("result").get("action") != "yahooWeatherForecast":
        return {}
    baseurl = "https://query.yahooapis.com/v1/public/yql?"
    yql_query = makeYqlQuery(req)
    if yql_query is None:
        return {}
    yql_url = baseurl + urllib.urlencode({'q': yql_query}) + "&format=json"
    result = urllib.urlopen(yql_url).read()
    data = json.loads(result)
    res = makeWebhookResult(data)
    return res


def makeYqlQuery(req):
    result = req.get("result")
    parameters = result.get("parameters")
    city = parameters.get("geo-city")
    if city is None:
        return None

    return "select * from weather.forecast where woeid in (select woeid from geo.places(1) where text='" + city + "')"


def makeWebhookResult(data):
    query = data.get('query')
    if query is None:
        return {}

    result = query.get('results')
    if result is None:
        return {}

    channel = result.get('channel')
    if channel is None:
        return {}

    item = channel.get('item')
    location = channel.get('location')
    units = channel.get('units')
    if (location is None) or (item is None) or (units is None):
        return {}

    condition = item.get('condition')
    if condition is None:
        return {}

    # print(json.dumps(item, indent=4))

    speech = "Today in " + location.get('city') + ": " + condition.get('text') + \
             ", the temperature is " + condition.get('temp') + " " + units.get('temperature')

    print("Response:")
    print(speech)

    return {
        "speech": speech,
        "displayText": speech,
        # "data": data,
        # "contextOut": [],
        "source": "apiai-weather-webhook-sample"
    }


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))

    print "Starting app on port %d" % port

    app.run(debug=False, port=port, host='0.0.0.0')
