#!/usr/bin/env python

from apns import APNs, Frame, Payload
from tinydb import TinyDB, Query, where
from pymongo import MongoClient

import pymongo
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

DB_FILE = 'db.json'

@app.route('/', methods=['GET','POST'])
def index():
    print("INDEX")
    res = '{"status":"OK"}'
    r = make_response(res)
    r.headers['Content-Type'] = 'application/json'
    return r

@app.route('/alexa', methods=['GET','POST'])
def alexa():
    exit = {"status":"OK"}
    shouldFinish = False
    try:
        output = ''
        print("ALEXA")
        data = request.data
        print(data)
        if data:
            obj = json.loads(data)
            inputData = {
                "inputSource": 'alexa',
                "userId": obj['session']['user']['userId'],
                "action": '',
                "intent": obj['request']['intent']['name'],
                "parameters": obj['request']['intent']['slots'],
                "incomplete": False,
                "response": '',
                "input": ''
            }
            for i in inputData["parameters"].keys():
                inputData["parameters"][i] = inputData["parameters"][i]["value"]
            response = evaluate(inputData)
            message = response['message']
            shouldFinish = response['shouldFinish']
            print(output)
        exit = {
            'version': '1.0',
            'sessionAttributes': {},
            'response': {
                'outputSpeech': {
                    'type': 'PlainText',
                    'text': message
                },
                'card': {
                    'type': 'Simple',
                    'title': "SessionSpeechlet - " + 'Title',
                    'content': "SessionSpeechlet - " + message
                },
                'reprompt': {
                    'outputSpeech': {
                        'type': 'PlainText',
                        'text': message
                    }
                },
                'shouldEndSession': shouldFinish
            }
        }
    except:
        print(sys.exc_info())
    res = json.dumps(exit)
    r = make_response(res)
    r.headers['Content-Type'] = 'application/json'
    return r

@app.route('/online', methods=['GET','POST'])
def online():
    print("ONLINE")
    try:
        params = request.args.to_dict()
        body = {"status": "INVALID", "code":""}
        if 'token' in params:
            body['status'] = 'OK'
            token = params['token']
            users = db_get_one('token', token)
            if users:
                user = users[0]
                if user['code']:
                    body['code'] = user['code']
                else:
                    body['code'] = generate_code(token)    
            else:
                body['code'] = generate_code(token)
        exit = {"statusCode": "200", "headers": {}, "body": json.dumps(body)}
        res = json.dumps(exit)
    except:
        print(sys.exc_info())
        res = "Error"
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
        "userId": '',
        "action": req['result']['action'],
        "intent": req['result']['metadata']['intentName'],
        "parameters": req['result']['parameters'],
        "incomplete": req['result']['actionIncomplete'],
        "response": req['result']['fulfillment']['speech'],
        "input": req['result']['resolvedQuery']
    }
    if inputData['inputSource'] == 'google':
        inputData["userId"] = req['originalRequest']['data']['user']['user_id']
    elif inputData['inputSource'] == 'facebook':
        inputData["userId"] = req['originalRequest']['data']['sender']['id']
    elif inputData['inputSource'] == 'slack_testbot':
        inputData["userId"] = req['originalRequest']['data']['user']
    elif inputData['inputSource'] == 'twitter':
        inputData["userId"] = req['originalRequest']['data']['direct_message']['recipient_id_str']
    elif inputData['inputSource'] == 'skype':
        inputData["userId"] = req['originalRequest']['data']['message']['user']['id']
    elif inputData['inputSource'] == 'telegram':
        inputData["userId"] = req['originalRequest']['data']['message']['from']['id']
        
    print(json.dumps(inputData, indent=4))
    
    response = evaluate(inputData)
    message = response['message']
    res = responseFormat(message)
    res = json.dumps(res, indent=4)
    print(res)
    
    r = make_response(res)
    r.headers['Content-Type'] = 'application/json'
    return r

def db_connect():
    db = MongoClient('mongodb://testuser:testpassword@ds117889.mlab.com:17889/desktox/test')
    return db

def tinydb_connect():
    return TinyDB(DB_FILE)

def db_get_one(field, value):
    db = db_connect()
    query = {}
    query[field] = value
    return db.find_one(query)

def tinydb_get_one(field, value):
    db = tinydb_connect()
    result = None
    results = db.search(where(field) == value)
    if results:
        result = results[0]
    return result

def db_get(field, value):
    db = db_connect()
    query = {}
    query[field] = value
    return db.find(query)

def tinydb_get(field, value):
    db = tinydb_connect()
    results = db.search(where(field) == value)
    return results

def db_update(values, field, value):
    db = db_connect()
    query = {}
    query[field] = value
    db.update_one(query,{"$set": values})

def tinydb_update(values, field, value):
    db = tinydb_connect()
    db.update(values, where(field) == value)

def db_insert(values):
    db = db_connect()
    db.insert_one(values)
    
def tinydb_insert(values):
    db = tinydb_connect()
    db.insert(values)

def db_remove(field, value):
    db = db_connect()
    query = {}
    query[field] = value
    db.delete_one(query)
    
def tinydb_remove(field, value):
    db = tinydb_connect()
    db.remove(where(field) == value)
    
def get_confirmation_code(source, userId, code):
    res = ''
    users = db_get('code', code)
    if users:
        values = {'code': ''}
        values[source] = userId
        db_update(values, 'code', code)
    else:
        res = "Your confirmation code is incorrect, " \
            "please provide me the confirmation code again, " \
            "by saying, The confirmation code is, and followed by " \
            " the number"
    return res

def get_random_number():
    return ''.join(["%s" % random.randint(0, 9) for num in range(0, 4)])

def generate_code(token):
    while True:
        code = get_random_number()
        codes = db_get('code', code)
        if not codes:
            break
    db_insert({'token':token,'code':code,'userId':''})
    return code

def evaluate(data):
    message = data['response']
    userId = data['userId']
    source = data['inputSource']
    user = db_get_one(source, userId)
    method = data['intent']
    shouldFinish = False
    if method == 'WelcomeIntent':
        if not user:
            message = "Welcome, I can see that you are a new user. In order to " \
                "be able to work with you, you need to install a Mac OS App, " \
                "if you have already installed it please provide me the " \
                "confirmation code by saying, The confirmation code is, " \
                "and followed by the separated four numbers"
        if not message:
            message = "Welcome back my friend, I am able to control your computer. Please tell me what do you want to execute by saying, execute open."
    elif method == 'MyColorIsIntent':
        if not user:
            message = "You received a confirmation code when the Mac OS " \
                "application was intalled, please provide me the " \
                "confirmation code by saying, The confirmation code is, " \
                "and followed by the separated four numbers"
        else:
            if not message:
                message = "Your command will be executed in a moment."
            action = data['parameters']['Color']
            token = user['token']
            send_message(action, token)
            shouldFinish = True
    elif method == 'ConfirmationCodeIntent':
        code = data['parameters']['Code']
        hasErrors = get_confirmation_code(source, userId, code)
        if hasErrors:
            message = hasErrors
        if not message:
            message = "I have confirmed successfully your confirmation code, please ask me to execute something by saying, execute open."
    return {"message": message, "shouldFinish": shouldFinish}

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

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))

    print "Starting app on port %d" % port

    app.run(debug=False, port=port, host='0.0.0.0')
