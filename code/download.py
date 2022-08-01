import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
import os
import pandas as pd
import xlsxwriter
import openpyxl 
import json
import numpy as np
import shutil
from datetime import datetime
from os import listdir
from os.path import isfile, join


LOCAL = False
FORMAT = "csv" # or "xlsx"


if LOCAL: 
    # for local instance
    RECORD_DIR = "/Users/caoming/media/trans/records"
    DOWNLOAD_DIR = "/Users/caoming/media/trans/image"
    RECORD_CONCISE = "/Users/caoming/media/trans/records/records_concise"
    RECORDS_VISITED = "/Users/caoming/media/trans/records/records_visited/visited.csv"
    
    RECORDS_NEWEST = f"/Users/caoming/media/records/records_newest/records_fl_inverse.{FORMAT}"
    RECORDS_PREVIOUS_BASE = "/Users/caoming/media/records/records_previous/"
    RECORDS_COPIES_PATH = "/Users/caoming/media/records_copies/"
    DOWNLOAD_DEFAULT_DIR = "/Users/caoming/media/newspapers"
    PARENT_PATH = "/Users/caoming/media/newspapers/"

    options = webdriver.ChromeOptions()
    preferences = {"download.default_directory": DOWNLOAD_DEFAULT_DIR,
    "download.prompt_for_download": False,} # download location
    options.add_experimental_option("prefs",preferences)
    options.add_argument("--headless")
    parent_path = PARENT_PATH
else: 
    # for ec2 instance
    RECORD_DIR = "/home/ec2-user/media/records/records_previous"
    DOWNLOAD_DIR = "/home/ec2-user/media/images"
    RECORD_CONCISE = "/home/ec2-user/media/records/records_concise"
    RECORDS_VISITED = "/home/ec2-user/media/records/records_visited/visited.csv"

    RECORDS_NEWEST = f"/home/ec2-user/media/records/records_newest/records_fl.{FORMAT}"
    RECORDS_PREVIOUS_BASE = "/home/ec2-user/media/records/records_previous/" 
    RECORDS_COPIES_PATH = "/home/ec2-user/media/records_copies/"
    DOWNLOAD_DEFAULT_DIR = "/home/ec2-user/media/newspapers"
    PARENT_PATH = "/home/ec2-user/media/newspapers/"

    options = webdriver.ChromeOptions()
    preferences = {"download.default_directory": DOWNLOAD_DEFAULT_DIR,
    "download.prompt_for_download": False,} # download location
    options.add_experimental_option("prefs",preferences)
    options.add_argument("--headless")
    parent_path = PARENT_PATH



'''
@param: 
mypath - the dir name that contains all record files
@return: 
df_total: a concise list of records, no duplicates, sorted by name
dir_files: files currently in the dir
previous_files_path: the record files used to generate current concise record file,ie. previously, what we use to generate the df_concise
'''
def read_files(dirpath, previous_files_path):

    # what are the stored previous files
    try:
        previous_files = pd.read_csv(previous_files_path).file_included
        previous_files = list(previous_files)   
    except FileNotFoundError as e:
        print("Error: first time, no previous files that have been aggregared into df_concise", type(e))
        first_time = True

    # what's currently in the dir
    dirfiles = [dirpath+"/"+f for f in listdir(dirpath) if isfile(join(dirpath, f))]

    # if the number of the previous files making up the reduced record file is the same as the number currently in the dir,
    # we take the already produced df_total
    if first_time == False and len(previous_file) == len(dirfiles):
        df_total = pd.read_csv(RECORD_CONCISE+"/records_concise.csv") 
        return df_total

    
    for f in dirfiles:
        df = pd.read_csv(f)
        # initialize a container
        if f == dirfiles[0]:
            df_total = df
        else: 
            df_total = pd.concat([df_total, df])
        print(f"{f} parsed")

    df_total = df_total.drop_duplicates(subset=['url']).sort_values(by = ['person','page_number'])
    df_total.to_csv(RECORD_CONCISE+"/records_concise.csv", index = False)


    dirfiles = pd.DataFrame(dirfiles, columns=["file_included"])
    dirfiles.to_csv(RECORD_CONCISE+"/source_files.csv")

    return df_total, dirfiles
        


def title_generator(sb, date, article_url):
    title = sb.replace(" ", "_")+"_"+ date 
    title = title.replace("/","_")
    encoded_url = article_url.replace("/","$") # We had to encode the url so that computer doesn't think the / means diretories, so the computer can find the right path!
    title = title + "_" + encoded_url
    return title



'''
@param: 
dirpath - folder in which all the record files are stored
download_path: folder in which subfolders for each person are stored
downloaf the image of each url into folders of each person
'''
def download(dirpath, previous_files_path, download_path):

    if LOCAL: 
        driver = webdriver.Chrome(executable_path= "/usr/local/bin/chromedriver", options = options) # for local instance
    else:
        driver = webdriver.Chrome(chrome_options = options) # for ec2 instance
    

    df, onlyfiles = read_files(dirpath, previous_files_path)

        
    try:
        visited = pd.read_csv(RECORDS_VISITED)  
        # only keep the uncommon roles between visited and df_concise
        df = pd.concat([visited, df]).drop_duplicates(keep=False)
        """    
        print("resplitting the large record file")
        for i,chunk in enumerate(pd.read_csv("/home/ec2-user/media/records/records_concise/records_concise.csv", chunksize=1000, dtype=dtypes)):
            chunk.to_csv('/home/ec2-user/media/records/records_concise/resplit/chunk{}.csv'.format(i), index=False)
        """
    except FileNotFoundError as e:
        print("Error: first time, no visited file", type(e))
        first_time = True

  
    df = df.reset_index()
    for index, row in df.iterrows():
        print(f"[ROW] {index}")
        
        url = row["url"]
        date = row["date"]
        sb = row["person"]

        if first_time == False and url in visited["url"]:
            print(f"\t\t\tImage src already visited {url}")
            #driver.back()
            continue #if we've already visited this url

        driver.get(url)

    #-----------------------------individual article page ---------------------------------
        img = None
        img_exists = True
        try: 
            img = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "BRnoselect")))
        except Exception: 
            print("Exception occured: the page_url is : ", driver.current_url)
            img_exists = False

        if img_exists == False: 
            print(f"Error: exception occured, cannot find image. {img}")
            #driver.back()
            continue
        
        src = img.get_attribute('src')
        response = requests.get(src, stream=True, headers={'User-Agent': 'Mozilla/5.0'})
        date = date.split(", ")[0] # get the right string out of the date object for an article
        title = title_generator(sb, date, url) # generate a title
        sb_dir = download_path + f"/{sb.replace(' ', '_')}"
        new_path = sb_dir+f"/{title}.jpg"

        # download the image
        if os.path.exists(sb_dir) == False:
            os.makedirs(sb_dir)
        with open(new_path, "wb+") as output:
            output.write(response.content)


        # visited keeps track of what pages we have visited. 
        file_exists = os.path.exists(new_path)
        if file_exists == False:
            print("Error: File not downloaded!")
            print(row)
            return row
            sys.exit()
            
        if index == 0:
            visited = row
        else:
            visited = pd.concat([visited, row])

    visited.to_csv(RECORDS_VISITED)
    
    #--------------------------------------------------------------------------------------
    
  



download(RECORD_DIR, RECORDS_VISITED, DOWNLOAD_DIR)