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
import csv

### currently in use on local testing
### NOTE: before start: search for  "for local instance" or "for ec2 instance", comment and uncomment the corresponding lines ###

LOCAL = False
FORMAT = "csv" # or "xlsx"
FOLD = "fold_5" # have to match with the .sh file 's log folds. 
                # eg. if we run fold_2.sh, FOLD has to be "fold_2"

if LOCAL: 
    # for local instance    INPUT =  f"/Users/caoming/media/input_data/{FOLD}.xlsx"
    RECORDS_NEWEST = f"/Users/caoming/media/records/records_newest/{FOLD}.{FORMAT}"
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
    INPUT = f"/home/ec2-user/media/input_data/{FOLD}.xlsx"
    RECORDS_NEWEST = f"/home/ec2-user/media/records/records_newest/{FOLD}.{FORMAT}"
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


# ========================= useful methods =====================================
# create a representation of a name in different format
class Person:
    def __init__(self, full_name): 
        self.full_name = full_name
        self.namelist = full_name.split(" ")
        self.first_name_1 = self.namelist[0] # if we wanna search only the first word in the name
        
        self.first_name_2 = self.namelist[0] + " " + self.namelist[1] # search the first 2 words in the name
        self.last_name_1 = self.namelist[-1] # search the last word in the name
        self.last_name_2 = self.namelist[-2] + " " + self.namelist[-1] # search the last 2 words in the name
        #print(self.first_name_1, self.first_name_2, self.last_name_1, self.last_name_2)

    def which_name_fraction(self, opt):
        if opt == "first_name_1": 
            output = self.first_name_1
            print("what is the output", output)
            return output
        elif opt == "first_name_2": 
            output = self.first_name_2.replace(" ", "%20")
            print("what is the output", output)
            return output
        elif opt == "last_name_1": 
            output = self.last_name_1
            print("what is the output", output)
            return output
        elif opt == "last_name_2": 
            output = self.last_name_2.replace(" ", "%20")
            print("what is the output", output)
            return output
        else: 
            print("ohno")
            return None

def make_folder(sb, parent_path):
    dir_name = sb.first_name_2
    dir_name = dir_name.replace(" ", "_")
    parent_dir = parent_path+dir_name
    #path = os.path.join(parent_dir, directory_name)
    try: 
        os.mkdir(parent_dir)
        print(f"We've made a folder for{sb.full_name}")
        return parent_dir
    except FileExistsError:
        print(f"Folder exists for {sb.full_name}, NO new folder")
        return parent_dir

# returns a list of string:
# example: name_str = Adriana Serafim Verbicário dos Santos
# returns: ['Adriana Serafim Verbicário dos Santos', 
# 'Adriana Verbicário dos Santos','Adriana Serafim dos Santos','Adriana Serafim Verbicário Santos'
# 'Adriana Santos',]
def ite(name_str): 
    storage = [] # stores all names with ith words left out
    
    name_list = name_str.split(" ")
    words = len(name_list)
    middle_name_length = words-2
    dic = {}

    storage.append(name_str) # append the full name
    if words <= 2:  # is the name is short, we don't explore the variations
        return storage
    for k in range (2, words): # end index - the 2nd to the last
        for i in range(1, k+1): # word index (1-k, inclusive), the word we want to start escape, we can escape the kth end word
            for n in range(1, k-i+2): # n- number of words to escape, the largest n will delete the kth
                if i+n < k+1:
                    #print(f"start = {i}, span = {n}, end = {k}")
                    new_list_skipn = name_list[:i] + name_list[i+n:k+1]
                    new_name = " ".join(new_list_skipn)
                    #print(new_name)
                    if not new_name in dic.keys() and len(new_list_skipn)!=1: # no duplicates and no single word
                        storage.append(new_name) 
                        dic[new_name] = 1
                elif i+n >= k+1: 
                    #print(f"start = {i}, span = {n}, end = {k}")
                    new_list_skipn = name_list[:i]
                    new_name = " ".join(new_list_skipn)
                    if not new_name in dic.keys() and len(new_list_skipn)!=1: # no duplicates and no single word
                        storage.append(new_name) 
                        dic[new_name] = 1
                    #print(new_name)
                    dic[new_name] = 1


    list_storage = [name.split(" ") for name in storage]  
    list_storage.sort(key = len, reverse= False)
    #print(list_storage)
    storage = [" ".join(mini_list) for mini_list in list_storage]
    #("NAME VARIARIONS:", storage)
    remove = False
    for s in storage:
        word = s.split(" ")
        if len(word) == 2:
            for w in word:
                if len(w) <= 3: 
                    remove = True
                    storage.remove(s)
    return storage


def ite_fl(name_str): 
    name_list = name_str.split(" ")
    name_first = name_list[0]
    name_last = name_list[-1]
    name = name_first +" " + name_last
    return name

def title_generator(sb, date, article_url):
    title = sb.first_name_2.replace(" ", "_")+"_"+ date 
    title = title.replace("/","_")
    encoded_url = article_url.replace("/","$") # We had to encode the url so that computer doesn't think the / means diretories, so the computer can find the right path!
    title = title + "_" + encoded_url
    return title
        

def record_file_name_generator(record_path): 
    s = record_path
    l = s.split("/")
    n = l[-1]
    return n

def copy_record_path_generator(RECORDS_PREVIOUS_BASE, record_path, FOLD):
    t = datetime.now()
    record_file_name = record_file_name_generator(record_path)
    copy_record_identifier = str(int(datetime.timestamp(t)))
    if "xlsx" in record_path: 
        copy_record_path = RECORDS_PREVIOUS_BASE + FOLD + "_" + copy_record_identifier + ".xlsx"
    else: 
        copy_record_path = RECORDS_PREVIOUS_BASE + FOLD + "_" + copy_record_identifier + ".csv"
    return copy_record_path

def previous_info_getter(record_format):
    if "xlsx" in record_format: 
        record = pd.read_excel(record_format)
    elif "csv" in record_format: 
        record = pd.read_csv(record_format)

    pick_bottom_name = record.iloc[-1, 2]
    pick_bottom_full_name = record.iloc[-1, 1]
    pick_bottom_nv = record.iloc[-1, 3]
    pick_bottom_pn = record.iloc[-1, 4]
    pick_bottom_url = record.iloc[-1, 6]

    return pick_bottom_name, pick_bottom_nv, pick_bottom_pn, pick_bottom_url, pick_bottom_full_name


def writer(record_format, mode, new_row = None, old_list=None):
    """
    record_format: is the record_path, we decide which file format to use based on .csv or .xlsx
    mode is either: "new" - create a new file if no record_format is present, only contains the header
                    "w" - overrite a old file: nothing is remained, but the new record is included
                    "a" - append to the old file: with all old info present: have to specify the old_list param. 
    new_row: list,  the new row to add
    old_list: the original info in the record_format
    """

    first_row = ["newspaper", "person", "name_variation", "page_number", "date","url", "previous page"] # header

    if "xlsx" in record_format: 
        if mode == "new": # open a new file with only the header
            with pd.ExcelWriter(record_format) as writer:  
                first_row = pd.DataFrame(np.reshape(first_row, (1,7)), index= [0], columns=[0,1,2,3,4,5,6])
                first_row.to_excel(writer, sheet_name='Sheet_name_1')
            print(f"xlsx New sheet created.")
        if mode == "w":  # overwrite but with the new row info and the header
            with pd.ExcelWriter(record_format) as writer:  
                rows = [first_row, new_row]
                rows = pd.DataFrame(np.reshape(rows, (2,7)), index= [0,1], columns=[0,1,2,3,4,5,6])
                rows.to_excel(writer, sheet_name='Sheet_name_1')
            print(f"\txlsx Records file overwritten due to too many lines.")
        elif mode == "a": # append to file
            new = []
            new.extend(old_list)
            new.append(new_row)
            with pd.ExcelWriter(record_format,  engine="openpyxl", mode='a', if_sheet_exists = 'replace') as writer: 
                new = pd.DataFrame(new)
                new.to_excel(writer, sheet_name='Sheet_name_1')
            print(f"\txlsx Records file appended")

    elif "csv" in record_format: 
        if mode == "new":
            with open(record_format, 'w') as f:
                writer = csv.writer(f)
                writer.writerow(first_row)
                print(f"\tcsv New sheet created.")
        if mode == "w":
            with open(record_format, 'w') as f:
                writer = csv.writer(f)
                writer.writerow(first_row)
                writer.writerow(new_row)
                print(f"\tcsv Records file overwritten due to too many lines.")
        elif mode == "a":
            with open(record_format, "a") as f:
                writer = csv.writer(f)
                writer.writerow(new_row)
                print(f"\tcsv Records file appended.")

def record_info(record_format, full_name, name, page_num, date, artical_url, current_url, RECORDS_PREVIOUS_BASE):
    """
    record the new info depending on the length of the old records
    """
    try:  
        new_row = ["estadao", full_name, name, page_num, date, artical_url, current_url]
        old_data = read_record(record_format)
        old_list = old_data.values.tolist()
        old_list = [ ele[1:] for ele in old_list]

        save_old = False
        
        if len(old_list) >= 1000:
            save_old = True

        if save_old == False: 
            # append to the old records file with old info, don't save another copy
            writer(record_format, "a", new_row = new_row, old_list=old_list)
        else: 
            # save the old records file
            # if there are more than 1000 entries in the record file, copy and save it with timestamp identifier
            copy_record_path = copy_record_path_generator(RECORDS_PREVIOUS_BASE, record_format, FOLD)
            shutil.copyfile(record_format, copy_record_path) 
            print(f"Over 3000 entries:\n\tCopy path: {copy_record_path}")

            # overwite the original record file with only the new record 
            writer(record_format, "w", new_row = new_row, old_list=None) 

    except FileNotFoundError as e:
        print("Error: still no record file to append to!", type(e))


def read_record(record_path):
    record = None
    if "xlsx" in record_path: 
        record = pd.read_excel(record_path)
    elif "csv" in record_path: 
        record = pd.read_csv(record_path)

    if record is None:
        print("CANNOT read the record!")
    return record


# this method will visit all newspapers (on different pages) related to a person
# it's set to an experimental mode where I only visit the first page for each name
def sb_s_news(full_name, record_path, pick_bottom_name_variation = None, pick_bottom_page_num = None, pick_bottom_url = None, repeated_url = None): 
    ru = repeated_url
    sb = Person(full_name)
    # the following properties can only eliminate repetitive download caused by name variations
    # they cannot detect if the jpg exits in the computer
    src_collection = []
    #article_list = [] # checks if a url has been clicked on earlier due to overlaps of paper for different name variations. NOTE that if the search was interrupted, repetitions in the first half cannot be detected. 
    record_urls = []


    name_fl= ite_fl(full_name)
    # if we are at the person/full_name that we didn't finish exploring last time: we truncate the name variation list so that we don't repeat searching for the variations that we searched last time
    """ 
    if pick_bottom_name_variation!=None: 
        index = name_variations.index(pick_bottom_name_variation)
        left_name_variations = name_variations[index:] # only check the last explored and unexplored name_variations. 
        if index!=0:
            print(f"Length of original name_variation list is {len(name_variations)}, length after trunction is {len(left_name_variations)}.")
        name_variations = left_name_variations
    """
    #for name in name_variations: 
        # if we are re-exploring the person that we didn't finish: meaning pick_bottom_name_variation != None
        # and if we are at the particular name_variation of that person we explored halfway (the first name in the truncated name_variation list), we directly go to that page number. 
    name = name_fl # there is only one variation--> first and last name
    if pick_bottom_name_variation != None and name.replace(" ", "+") == pick_bottom_name_variation:
        start_page = pick_bottom_page_num # pick_bottom_name_variation != None means pick_bottom_page_num != None
    else:
        start_page = 1

    
    print(f"This search is based on: {name}")
    name = name.replace(" ", "+")

    #name = "%22"+name+"%22"
    decade = "2010"

    page = f"{start_page}" # start_page in string format
    # this is the template for exact search
    sb_URL = f"https://acervo.estadao.com.br/procura/busca.php?&busca={name}&decade=2010%7C2010&page={page}"
    # template: https://acervo.estadao.com.br/procura/busca.php?&busca={name}&opt=&containExactPhrase=lava%20jato&decade=2010%7C2010&opt=&containExactPhrase=lava%20jato&page=3

    if LOCAL: 
        driver = webdriver.Chrome(executable_path= "/usr/local/bin/chromedriver", options = options) # for local instance
    else:
        driver = webdriver.Chrome(chrome_options = options) # for ec2 instance
    
    driver.get(sb_URL)
    # ---------------------------For one person-----------------------------------
    # make a directory for that person, for now we don't need it when collecting urls
    """
    path = make_folder(sb, parent_path) # fetch the absolute address for the folder we made for that person
    """
    # get last page number
    try:
        last_page = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, "//span[@class='page-ultima-qtd']")))
        last_page = int(last_page.text)
        print("\tWhat is the maximum page number?", last_page)
    except:
        print(f"\tOnly one page of articles found for {full_name}")
        last_page=1

    # iterate over all pages on the bottom search bar
    for page_num in range(start_page, last_page+1): 

        """ # not for ec2, for local instance
        if page_num > 2:
            break"""
        
        """ 
        # save the record file every 20 pages
        if page_num % 20 == 0:
            src = record_path
            # where I wanna save the copies to
            dst = f"{RECORDS_COPIES_PATH}var{name}_up2p{page_num}.xlsx"  
            shutil.copyfile(src, dst) 
        """
        # ---------- flip page ------------------------------------------
        if last_page !=1:
            page_num_str = f"{page_num}" # start_page in string format
            # this is the template for exact search
            sb_URL_flip =f"https://acervo.estadao.com.br/procura/busca.php?&busca={name}&decade=2010%7C2010&page={page_num_str}"
            #sb_URL_flip =f"https://acervo.estadao.com.br/procura/busca.php?&busca={name}&opt=&containExactPhrase=lava%20jato&decade=2010%7C2010&opt=&containExactPhrase=lava%20jato&page={page_num_str}"
            
            if LOCAL: 
                driver = webdriver.Chrome(executable_path= "/usr/local/bin/chromedriver", options = options) # for local instance
            else:
                driver = webdriver.Chrome(chrome_options = options) # for ec2 instance
    
            
            driver.get(sb_URL_flip)
            current_url = driver.current_url
            try:
                last_page = WebDriverWait(driver, 2).until(
                            EC.element_to_be_clickable((By.XPATH, "//span[@class='page-ultima-qtd']")))
                last_page = int(last_page.text)
                print("\tWhat is the maximum page number?", last_page)
            except Exception as e: 
                print('last page cannot be extracted!')
            print(f"\tPAGE# {page_num}; current_url : {current_url}; last page: {last_page}")
        #  if last_page == 1, we onlu found 1 page, then we do not flip page
        else: 
            current_url = driver.current_url
                
        
        papers = driver.find_elements(By.XPATH, "//a[@title='LEIA ESTA EDIÇÃO']") # find links for all articles on one page
        link1 = len(papers)
        try: 
            if link1 ==0:
                print(f"\t\tNo article fould for {name} on page# {page_num}")
                continue
        except Exception:
            print("\t\tlink equation******")

        this_page_url_list = []
        for paper in papers: 
            paper_url = paper.get_attribute('href') # url
            this_page_url_list.append(paper_url)

        start_paper_index = 0
        # if we are searching the person we didn't finish last time, 
        # searching the person's specific name variation we didn't finish, 
        # and the specific page of that name_variation's search result
        # note that we cannot repeate search for this bottom url at each page after the start page
        if pick_bottom_name_variation != None and name == pick_bottom_name_variation and page_num == pick_bottom_page_num and page_num != start_page:
            url_index =  this_page_url_list.index(pick_bottom_url) # check where we left previously
            start_paper_index = url_index+1 # we skip the url that we already visited. 
            print(f"\t\tCONTINUE SEARCH: from person: {full_name}, from variation: {pick_bottom_name_variation},from page: {pick_bottom_page_num}, from the {start_paper_index}th paper on that page.")
            
        # what if we resume at the last paper of a page? 
        if start_paper_index == len(papers): 
            print("DEBUG: we are at the last paper!!! last page is finished! \n\n\n")

        # for paper i
        for i in range(start_paper_index, len(papers)): 
            print(f"\t\tPaper-Round {i}: {name}")
            papers = driver.find_elements(By.XPATH, "//a[@title='LEIA ESTA EDIÇÃO']") # links for all articles on one page
            link2 = len(papers)
            # fetch info for a individual newspaper: link and date
            print(f"\t\t\tpaper = papers[i] : i={i}")
            paper = papers[i] # access a certain link
            #print("what is that out-of-the-range index", i)
            
            #=========================================check repetitive urls================================================================
            artical_url = paper.get_attribute('href') # url
            """
            if artical_url in article_list: # article_list is an accumulation of this person's articles in this search, including the articles from all variations
                print(f"\t\t\tpaper #{i} has been clicked on within variations. caught by article_list. continue to next paper #{i+1} in a list of {link2}")
                continue # continue to next url
            else:
                print(f"\t\t\tpaper #{i} has NOT been clicked on within variations. append to url-list and go in...")
            """
            try:  
                # try to Append DataFrame to existing excel file
                old_data = read_record(record_path)
                record_urls = old_data.iloc[:, 5]
                record_urls = list(record_urls) 
                if artical_url in record_urls: 
                    ru +=1
                    print(f"\t\t\tpaper #{i} has been clicked on. continue to next paper #{i+1} in a list of {link2}\n\t\t\t\tTotal repeated url = {ru}")
                    continue
            except FileNotFoundError as e:
                print("Error: still no record file to append to!", type(e))
            #article_list.append(artical_url)
            print(f"\t\t\tthis article url is {artical_url}")
            #=========================================================================================================
            
            #============================================excel or csv stuff============================================
            # keep records of the new info scrapped. 
            # obtain the date
            dates = driver.find_elements(By.TAG_NAME, "em") # dates for all articles on one page
            date = dates[i].text # date of a specific paper
            record_info(record_path, full_name, name, page_num, date, artical_url, current_url, RECORDS_PREVIOUS_BASE)
            #==========================================================================================================

            # since we are now only collecting urls, so for now we don't download the image
            """ 
            paper.click() 

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
                driver.back()
                continue
            
            src = img.get_attribute('src')

            if src in src_collection:
                print(f"\t\t\tImage src already visited {src}")
                driver.back()
                continue #if we've already visited this src

            src_collection.append(src)
            response = requests.get(src, stream=True, headers={'User-Agent': 'Mozilla/5.0'})
            date = date.split(", ")[0] # get the right string out of the date object for an article
            title = title_generator(sb, date, artical_url) # generate a title
            new_path = path + f"/{title}.jpg"

            with open(new_path, "wb+") as output:
                output.write(response.content)
            
            #--------------------------------------------------------------------------------------
            
            driver.back() # exit the individual newspaper page, back to page i with many newspapers
            """
    driver.quit()       
    print(f"we've explored name {name} as the only variation for {full_name}---------------\n\n")
    """except Exception:
            print(driver.current_url)
            print(Exception)
            print("we return!")
            return
    """
    print(f"we've exhausted all variations of {full_name}\n----------------------------------------------\n\n\n")
    return ru

# data frame of names
def feed_all_names(df, record_path):
    repeated_url_count = 0
    
    where=-1 # initialize; where should be the row number in the worksheet we opened
    # -------------check where we are in excel, if there is one --------------------
    try: # if the excel file already exists
        pick_bottom_name, pick_bottom_nv, pick_bottom_pn, pick_bottom_url, pick_bottom_full_name = previous_info_getter(record_path)
        print(f"what is the bottom name? {pick_bottom_name};\nWhat is the specific variation? {pick_bottom_nv};\nWhat is the page? {pick_bottom_pn};\nWhat is the last url? {pick_bottom_url}.")
        print(f"Is Where effective? {list(df['Réu']).index(pick_bottom_full_name)}")
        where = list(df['Réu']).index(pick_bottom_full_name)
    except FileNotFoundError as e: # if the excel file is not present
        print('Error excepted!, no record file which should record the people we went over',type(e), " SO we create a new records")
        writer(record_path, "new") #create a new file with only the header
        record = read_record(record_path)
    print(f"what is where: {where}\n\n") # -1 means we had not explored any name yet

    start_all_from_the_beginning= False
    if where == -1:
        print("START SEARCHING for the 1st time!!!")
        where = 0 
        start_all_from_the_beginning = True

    # iterate over each person
    for ind in range(where, len(df)): # we revisit the articles of the person that we didn't finish exploring last time
        full_name = df['Réu'][ind]
        print(f"[{ind}] NAME: {full_name}")

        # starting all over
        if ind == 0 and ind == where and start_all_from_the_beginning == True:
            print("RESTART")
            repeated_url_count += sb_s_news(full_name, record_path, repeated_url=repeated_url_count) 
        # we did not finish the first persomn earlier, so re-search the 1st person
        elif ind == 0 and ind == where and start_all_from_the_beginning == False:
            print(f"Re-search the 1st person: start person: {full_name}, start variation: {pick_bottom_nv}, start page: {pick_bottom_pn}.")
            repeated_url_count += sb_s_news(full_name, record_path, pick_bottom_name_variation = pick_bottom_nv, pick_bottom_page_num = pick_bottom_pn, pick_bottom_url = pick_bottom_url, repeated_url=repeated_url_count)
        # We RESUME, RE-explore that unfinished person
        elif ind != 0 and ind == where: 
            print(f"RESUME, RE-explore that unfinished person: start person: {full_name}, start variation: {pick_bottom_nv}, start page: {pick_bottom_pn}.")
            repeated_url_count += sb_s_news(full_name, record_path, pick_bottom_name_variation = pick_bottom_nv, pick_bottom_page_num = pick_bottom_pn, pick_bottom_url = pick_bottom_url, repeated_url=repeated_url_count)
        # We RESUME, continue from the next person
        else: 
            print("RESUME, continue from the next person")
            repeated_url_count += sb_s_news(full_name, record_path, repeated_url=repeated_url_count) 

        """
        # after collecting one person
        src = record_path
        # where I wanna save the copies to
        dst = f"{RECORDS_COPIES_PATH}copy_name_save_{ind}.xlsx" 
        shutil.copyfile(src, dst) 
        """
        
    
record_path = RECORDS_NEWEST
df = pd.read_excel(INPUT) 
if LOCAL:
    feed_all_names(df, record_path)
else: 
    error_count = 0
    feed_all_names(df, record_path)
"""while True: 
        try: 
            feed_all_names(df, record_path)
        except IndexError as index_error: 
            error_count+=1
            print(f"\n===================================\nINDEX ERROR OCCURED: \n{index_error}\nError Count = {error_count}\n===================================")
        except Exception as e: 
            error_count+=1
            print(f"\n===================================\nUNKNOWN ERROR OCCURED: \n{e}\nError Count = {error_count}\n===================================")

"""