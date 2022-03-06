#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import re
import string
import random
import sqlite3 as sl
import base64
from datetime import datetime
import datetime as dt
import argparse
from tabulate import tabulate
from collections import OrderedDict
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from currency_converter import CurrencyConverter
import time

class product:
  def __init__(self, name, cost, currency, url, session):
    self.name = name
    self.cost = cost
    self.currency = currency
    self.url = url
    self.session = session

HEADERS = ({'User-Agent':
            'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36',
            'Accept-Language': 'en-GB, en;q=0.5'})

Globalsession = ''.join(random.sample(string.ascii_lowercase, 20))
DatabaseName = 'productcompare.db'

######################################################################
## getamazonPrice
## Input: Amazon URL
## Output: Class of Name, Cost, Currency
######################################################################
def getamazonPrice(url):
  urls = re.findall('https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+', url)[0]
  match = re.match('https?:\/\/(www\.)?amazon\..{2,3}(.{2,3})?', urls)
  if not match:
    return "This is not a valid amazon URL."

  page = requests.get(url, headers=HEADERS)

  soup = BeautifulSoup(page.content, features="lxml")

  try:
    title = soup.find(id='productTitle').get_text().strip()
    verboseprint("Got the title: " + title)
    session = createSession("Amazon", title)
  except:
    verboseprint("It looks like Amazon have blocked the request.")
    return "Amazon have blocked the request."
  availability = soup.find(id='availability').get_text().strip()

  if availability.lower().find("currently unavailable.") == -1:
    try:
      priceFind = soup.find_all("span", class_="apexPriceToPay")
      priceFind = priceFind[0].text
      price = priceFind.__str__()

      counter = int(len(price)/2)
      pleft, pright = price[:counter], price[counter:]
      if pleft==pright:
        price = pleft
    except:
      try:
        price = soup.find_all("span", class_="a-offscreen")[0].text
      except:
        price = ''
  else:
    price = " Out of stock"

  return product(title, price[1:], price[:1], url, session)


######################################################################
## getebayPrice
## Input: Ebay URL
## Output: Class of Name, Cost, Currency
######################################################################
def getebayPrice(url):
  urls = re.findall('https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+', url)[0]
  match = re.match('https?:\/\/(www\.)?ebay\..{2,3}(.{2,3})?', urls)
  if not match:
    return "This is not a valid ebay URL."

  page = requests.get(url, headers=HEADERS)
  if page.encoding != 'utf-8':   
    page.encoding = 'utf-8'
  soup = BeautifulSoup(page.content, features="lxml", from_encoding='utf-8')
  try:
    title = (soup.find_all("h1", class_="x-item-title__mainTitle")[0].text).strip()
    verboseprint("Got the title: " + title)
  except: 
    verboseprint("Could not get "+url)
    return 1
  session = createSession("Ebay", title)

  price = soup.find_all("span", itemprop="price")[0].text

  price = ((price.lower()).replace("each","").strip())

  return product(title, price[1:], price[:1], url, session)

def randomDBTablename(x):
  rand = ''.join(random.sample(string.ascii_lowercase, x))
  return rand

def createSession(site, title):
  try:
    testdbconn()
  except:
    return "Database connection failed"
  title_bytes = (title).encode('ascii')
  base64_title = base64.b64encode(title_bytes).decode()
  con = sl.connect(DatabaseName)
  with con:
    c = con.cursor()
    if site == "Amazon":
      c.execute(''' SELECT name FROM PRODUCTS WHERE AmazonName='{name}' '''.format(name=base64_title))
    else:
      c.execute(''' SELECT name FROM PRODUCTS WHERE EbayName='{name}' '''.format(name=base64_title))
    try:
      session = c.fetchone()[0]
    except:
      session = Globalsession

    session = session+","+site
    verboseprint("session:"+session)
  return session

def createdbTable(): 
  con = sl.connect(DatabaseName)
  tablename = randomDBTablename(10)
  with con:
    con.execute("""
        CREATE TABLE {tablename} (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            productname TEXT,
            datetime TEXT,
            price INTEGER,
            currency TEXT, 
            sitevisited TEXT
        );
    """.format(tablename=tablename))
  return tablename

def posttodb(producttoadd): 
  now = datetime.now()
  datenow = now.strftime("%d/%m/%Y %H:%M:%S")
  try:
    title_bytes = (producttoadd.name).encode('ascii')
  except:
    return 1
  base64_title = base64.b64encode(title_bytes).decode()
  session = (producttoadd.session).split(",")[0]
  site = (producttoadd.session).split(",")[1]
  try:
    testdbconn()
  except:
    return "Database connection failed"
  con = sl.connect(DatabaseName)
  with con:
    c = con.cursor()
    c.execute(''' SELECT count(tableloc) FROM PRODUCTS WHERE name='{name}' '''.format(name=session))
    if c.fetchone()[0]==1:
      if session == Globalsession:
        c = con.cursor()
        c.execute(''' UPDATE PRODUCTS SET {site}Name = '{title}' WHERE name='{name}' '''.format(site=site, title=base64_title, name=session))
        con.commit()
      insertDB(producttoadd, session, datenow)
    else:
      newTable = createdbTable()
      c.execute(''' INSERT INTO PRODUCTS (name, added, tableloc, {site}Name) VALUES ('{name}', '{added}', '{tableloc}', '{title}') '''.format(
        site=site, name=session, added=datenow, tableloc=newTable, title=base64_title)
      )
      con.commit()
      insertDB(producttoadd, session, datenow)


def insertDB(producttoadd, base64_title, datenow):
  con = sl.connect(DatabaseName)
  with con:
    c = con.cursor()
    c.execute(''' SELECT tableloc FROM PRODUCTS WHERE name='{name}' '''.format(name=base64_title))
    table = c.fetchone()[0]
    c.execute(''' INSERT INTO {tablename} (productname, datetime, price, currency, sitevisited) VALUES ('{productname}','{datetime}','{price}','{currency}','{url}') '''.format(
      tablename=table, productname=producttoadd.name, datetime=datenow, price=producttoadd.cost, currency=producttoadd.currency, url=producttoadd.url)
    )
    con.commit()
  return None

def runsched(): 
  con = sl.connect(DatabaseName)
  with con:
    c = con.cursor()
    tables = c.execute(''' SELECT tableloc FROM PRODUCTS ''').fetchall()
    for table in tables:
      table = table[0]
      uniqueValues = c.execute(''' SELECT DISTINCT sitevisited FROM {tablename} '''.format(tablename=table)).fetchall()
      for value in uniqueValues:
        value = value[0]
        ematch = re.match('https?:\/\/(www\.)?ebay\..{2,3}(.{2,3})?', value)
        if ematch:
          eurl = value
        amatch = re.match('https?:\/\/(www\.)?amazon\..{2,3}(.{2,3})?', value)
        if amatch:
          aurl = value
      try:
        runBoth(aurl, eurl)
        verboseprint("Sleeping for 5 seconds so Amazon don't block us.")
        time.sleep(5)
      except:
        continue

def testdbconn(): 
  con = sl.connect(DatabaseName)
  with con:
    c = con.cursor()
    c.execute(''' SELECT count(name) FROM sqlite_master WHERE type='table' AND name='PRODUCTS' ''')
    if c.fetchone()[0]==1: 
      exists = True
    else:
      con.execute("""
          CREATE TABLE PRODUCTS (
              id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
              name TEXT,
              added TEXT,
              tableloc TEXT,
              AmazonName TEXT,
              EbayName TEXT
          );
      """)
      con.commit()

def getfromdb(label): 
  list = []
  con = sl.connect(DatabaseName)
  counter = 1
  with con:
    c = con.cursor()
    databaseInfo = c.execute(''' SELECT * FROM PRODUCTS ''').fetchall()
    for entry in databaseInfo:
      if entry[4] is not None:
        avalue = base64.b64decode(entry[4]).decode()
      else:
        avalue = ""
      if entry[5] is not None:
        evalue = base64.b64decode(entry[5]).decode()
      else:
        evalue = ""
      list.append(OrderedDict([("Index", str(counter)), ("Amazon Product", avalue), ("Ebay Product", evalue), ("Table Name", entry[3])]))
      counter = counter+1

    print(tabulate(list, headers='keys', tablefmt='fancy_grid'))
    f=lambda userinput: (userinput.isdigit() and ((int(userinput)<=(len(list)) and int(userinput)>=0) and userinput)) or f(input("invalid input. Try again\nPlease select an index {label}: ".format(label=label)))
    userinput = f(input("Please select an index {label}: ".format(label=label)))
    return list[int(userinput)-1]['Table Name']


def createChart():
  userselection = getfromdb("to create a chart from")
  print("")
  con = sl.connect(DatabaseName)
  with con:
    c = con.cursor()
    databaseInfo = c.execute(''' SELECT productname,currency,price,datetime,sitevisited FROM {tablename} '''.format(tablename=userselection)).fetchall()

  immutableList = list()
  immutableList.append(["Product Name", "Cost", "Checked", "Provider Checked"])

  for entry in databaseInfo:
    entryList = list(entry)
    entryList[4] = amazonorebay(entryList[4])
    entryList[1] = str(entryList[1])+str(entryList[2])
    del entryList[2]
    immutableList.append(entryList)
  if not notable:  
    print(tabulate(immutableList, headers="firstrow"))
  
  if not nochart:
    ecost = [convertCurrency(item[1]) for item in immutableList[1:] if item[3] == "Ebay"]
    acost = [convertCurrency(item[1]) for item in immutableList[1:] if item[3] == "Amazon"]

    edates = [item[2] for item in immutableList[1:] if item[3] == "Ebay"]
    adates = [item[2] for item in immutableList[1:] if item[3] == "Amazon"]
    
    allCosts = [item[1][1:] for item in immutableList[1:]]

    adates_formatted = []
    edates_formatted = []
    for each in adates:
      datesplit = (each.split(" ")[0]).split("/")
      timesplit = (each.split(" ")[1])
      adates_formatted.append(datesplit[1]+"/"+datesplit[0]+"/"+datesplit[2]+" "+timesplit)
    
    for each in edates:
      datesplit = (each.split(" ")[0]).split("/")
      timesplit = (each.split(" ")[1])
      edates_formatted.append(datesplit[1]+"/"+datesplit[0]+"/"+datesplit[2]+" "+timesplit)
    
    ay = mdates.datestr2num(adates_formatted)
    ey = mdates.datestr2num(edates_formatted)

    fig, ax = plt.subplots()

    plt.plot(ay, [float(all[1:]) for all in acost], '-bo', label="Amazon")
    plt.plot(ey, [float(all[1:]) for all in ecost], '-ro', label="Ebay")

    aused = set()
    eused = set()
    aunique = [x for x in acost if x not in aused and (aused.add(x) or True)]
    eunique = [x for x in ecost if x not in eused and (eused.add(x) or True)]

    for i in range(len(aunique)):
      plt.annotate(aunique[i], (ay[i], [float(all[1:]) for all in acost][i] + 1), fontsize=8, color = 'blue')
    
    for i in range(len(eunique)):
      plt.annotate(eunique[i], (ey[i], [float(all[1:]) for all in ecost][i] - 1.5), fontsize=8, color = 'red')

    ax.xaxis_date()
    fig.autofmt_xdate()
    plt.legend(loc="upper left")
    plt.ylim(float(min(allCosts))-10, float(max(allCosts))+10)

    plt.xlabel("Date price checked")
    plt.ylabel("Cost (£)")

    plt.show()
  
def convertCurrency(value):
  currencies = {'$': 'USD', '€': 'EUR', '£': 'GBP'}
  c = CurrencyConverter()
  if not currencies[value[0]] == 'GBP':
    cost = c.convert(value[1:], currencies[value[0]], 'GBP')
    cost = "£"+str(round(cost, 2))
  else:
    cost = value
  return cost

def amazonorebay(url): 
  if re.match('https?:\/\/(www\.)?ebay\..{2,3}(.{2,3})?', url):
    retval = "Ebay"
  elif re.match('https?:\/\/(www\.)?amazon\..{2,3}(.{2,3})?', url):
    retval = "Amazon"
  return retval

def productsuggestions(): 
  return None

def linktosession():
  selectedforlink = getfromdb("to link a product to")
  userinput = input("Please provide a link to the product you want to add: ")
  site = amazonorebay(userinput)
  con = sl.connect(DatabaseName)
  with con:
    c = con.cursor()
    c.execute(''' SELECT name FROM PRODUCTS WHERE tableloc = '{tablename}' '''.format(tablename=selectedforlink))
    sessiontoken = c.fetchone()[0]
  
  global Globalsession 
  Globalsession = sessiontoken

  verboseprint("Global session set to: " + Globalsession)
  if site == "Amazon":
    posttodb(getamazonPrice(userinput))
  elif site == "Ebay":
    posttodb(getebayPrice(userinput))

def removefromDB():
  toremove = getfromdb("to remove from tracking")
  f=lambda userinput: (isinstance(userinput, str) and ((userinput.lower() in ("y","n"))) and userinput) or \
  f(input("invalid input. Try again\nYou want to remove the table '{table}', are you sure [Y/n]: ".format(table=toremove)))
  userinput = f(input("You want to remove the table '{table}', are you sure [Y/n]: ".format(table=toremove)))

  if userinput.lower() == "y":
    con = sl.connect(DatabaseName)
    with con:
      c = con.cursor()
      try:
        c.execute(''' DROP TABLE {tablename} '''.format(tablename=toremove))
      except:
        verboseprint("{table} is already deleted.".format(table=toremove))
      c.execute(''' DELETE FROM PRODUCTS WHERE tableloc = '{tablename}' '''.format(tablename=toremove))
    con.commit()
    con.close()
  else:
    return

def runBoth(aurl, eurl):
  if not aurl == "":
    posttodb(getamazonPrice(aurl))
  if not eurl == "":
   posttodb(getebayPrice(eurl))

def argparser():
  parser = argparse.ArgumentParser(
    prog='PriceCompare',
    description='''The program will take 2 URL's, 1 for Amazon and 1 for Ebay. The program can then track these URL's for price changes and graph this over time. ''',
    epilog='''
      This is not a supported product and was created as a proof of concept.''')
  parser.add_argument("-s", "--schedule", action="store_true", help="Run the schedule to check prices for products already monitored.")
  parser.add_argument("-a", "--additems", action="store_true", help="Add new items to track, this will prompt for URL's.")
  parser.add_argument("-d", "--display", action="store_true", help="Display results in table and graph.")
  parser.add_argument("-nt", "--notable", action="store_true", help="Use with -d to display the chart only.")
  parser.add_argument("-nc", "--nochart", action="store_true", help="Use with -d to display the table only.")
  parser.add_argument("-l", "--link", action="store_true", help="Link a URL to an exisiting product.")
  parser.add_argument("-r", "--remove", action="store_true", help="Remove from database (stop tracking products).")
  parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose output.")
  args = parser.parse_args()
  global schedule
  schedule = args.schedule
  global verbose
  verbose = args.verbose
  global items
  items = args.additems
  global display
  display = args.display
  global remove
  remove = args.remove
  global link
  link = args.link
  global notable
  notable = args.notable
  global nochart
  nochart = args.nochart

def main():
  if schedule:
    runsched()
  elif items:
    print('Enter the amazon URL to track:')
    aurl = input()
    print('Enter the ebay URL to track:')
    eurl = input()
    runBoth(aurl, eurl)
  elif display:
    createChart()
  elif remove:
    removefromDB()
  elif link:
    linktosession()

argparser()
if verbose:
  def verboseprint(*args, **kwargs):
    print(*args, **kwargs)
else:
    verboseprint = lambda *a, **k: None # do-nothing function
main()