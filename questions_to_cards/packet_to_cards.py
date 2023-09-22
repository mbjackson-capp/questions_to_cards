from PyPDF2 import PdfReader
from docx import Document
from datetime import datetime
import re
import pandas as pd
import os
import time

from text_processing import tokenize_and_explode, cleanup
from utility import write_out

#TODO: put non-match group in proper place so output of re.split() doesn't
#produce a bunch of blanks
SPLIT_RE = re.compile(r"(?=ANSWER:)|" #answer line
                    r"(?<=\>)\s?[0-9]{1,2}\.\s|" #question-starting number
                    r"Tossups |"
                    r"Bonuses |"
                    r"\[10(?:e|m|h)\]\s?|\[(?:H|M|E)\]|" #part indicator
                    r"(?:__SPLIT__)")

#TODO: figure out a better way to deal with "Bonuses" in BHSU packet 1
DOCX_JUNK = r'\s+|<[^>]+>|Bonuses'


def file_to_cards(
        filename, 
        diff=None,
        yr=None,
        write_to_file=False,
        debug=False
):
    '''
    Function that converts a .docx or PDF to a dataframe of flashcards. Calls 
    on functions below as helper functions
    '''
    if '.pdf' in filename:
        file_text = pdf_to_text(filename)
    elif '.docx' in filename:
        file_text = docx_to_text(filename)   
    else:
        raise Exception(f"File type {filename[:-4]} is not supported")
    
    cards_df = text_to_cards(
        file_text, 
        diff=diff, 
        yr=yr, 
        write_to_file=write_to_file,
        debug=debug
    )

    return cards_df


def pdf_to_text(packet_filepath):
    '''
    Convert a packet of quizbowl questions in PDF format to a list that can
    then be passed into a card-creation function.

    Inputs:
        -packet_filepath(str): location of packet file to be read in
        -diff(str or int): difficulty ranking of set from 1 to 10, as defined
        by QBReader
        -yr(str or int): four-digit representation of packet's release year
        -split_up (boolean): whether to create cards at the clue level rather
        than the question/part level
    Returns (pandas DataFrame): DataFrame of cards
    '''

    reader = PdfReader(packet_filepath) 

    all_text = ''
    for page in reader.pages:
        all_text += page.extract_text()

    all_text = re.sub('\n', ' ', all_text) #remove spurious newlines
    all_text = re.sub('^.+(Tossups|TOSSUPS)', '', all_text) #remove authorship credits from top
    all_text = re.split(SPLIT_RE, all_text)

    return all_text


def docx_to_text(packet_filepath):
    '''
    Convert a .docx file into a list to be passed into card-creation function. 
    Inspired by qbreader doc-to-txt.py, by Geoffrey Wu
    '''
    #TODO: Check whether ANSWER: is in the right place (every odd-index up until
    # bonuses start, at which point it's 3-2-2 to account for bonus leadins)

    all_text = ""
    doc = Document(packet_filepath)
    for para in doc.paragraphs:
        all_text += (para.text + "__SPLIT__")
        #all_text += " "

    all_text = re.sub('\n', ' ', all_text) #remove spurious newlines
    all_text = re.sub('^.+(Tossups|TOSSUPS)', '', all_text) #remove authorship credits from top
    all_text = re.split(SPLIT_RE, all_text)
    for i, graf in enumerate(all_text):
        #TODO: handle category tags in some manner other than deleting if they
        #are present
        if re.match(DOCX_JUNK, graf) or graf == "":
            all_text[i] = "__DELETE__"
    all_text = [i for i in all_text if i != "__DELETE__"]

    return all_text


def text_to_cards(
        all_text: list,
        diff=None, 
        yr=None, 
        write_to_file=False,
        debug=False
        ):
    '''
    Take the output of pdf_to_text() or docx_to_text() and convert that list
    of strings into a DataFrame of clue-answer cards.
    '''
    clues = []
    answers = []
    for idx, segment in enumerate(all_text):
        # alternate clue-answer except for bonus leadins, which "leap ahead" to find 
        # the corresponding answer
        #TODO: create or import a more thorough FTPE_RE for edge cases and old questions
        #TODO: less dodgy way of dealing with the "Bonuses" in BHSU packet 1
        #TODO: deal with stray 'The theme of this bonus' type editors notes in a more
        #refined manner
        if (segment == 'Bonuses') or ('The theme of this bonus' in segment):
            continue
        elif ('or 10 points each' in segment or 
              'the stated number of points' in segment or
              'answer the following' in segment):
            clues.append(segment)
            #idx+2 looks ahead to answer line for part 1 of bonus
            leadin_ans = re.sub('ANSWER: ', '', all_text[idx+2])
            answers.append(leadin_ans)
        elif 'ANSWER: ' in segment:
            segment = re.sub('ANSWER: ', '', segment)
            answers.append(segment)
        else:
            clues.append(segment)

    if debug:
        for clue in clues:
            print(clue) 
            print('\n')
        print('\n')
        for ans in answers:
            print(ans)

    if len(clues) != len(answers):
        for i, clue in enumerate(clues):
            print(i, clue)
        for j, ans in enumerate(answers):
            print(j, ans)
        raise Exception(f"Mismatch: You have {len(clues)} clues and {len(answers)} corresponding answers")

    packet_df = pd.DataFrame({'clue':clues,
                            'answer':answers})

    #split up
    packet_df = tokenize_and_explode(packet_df)
    packet_df = cleanup(packet_df)

    packet_df.loc[:,'tags'] = ''
    if diff is not None:
        packet_df.loc[:,'tags'] += f"diff::{diff} "
    if yr is not None:
        packet_df.loc[:,'tags'] += f"yr::{yr} "
    packet_df.loc[:,'tags'] = packet_df.loc[:,'tags'].str.strip()

    packet_df.reset_index(drop=True, inplace=True)

    if write_to_file:
        now = datetime.now().strftime("%Y%-m%d-%H%M%S")
        filepath = f"test_output/packet_clues_{now}.csv"
        print(f"Writing clue cards to {filepath}...")
        write_out(packet_df, filepath)
        print("Write-out complete")
    else:
        return packet_df
    

def get_all_filenames(starting_dir):
    '''
    Walk a directory recursively and get out every file that could be a packet.
    Helper function for directory_to_cards().

    Closely modeled on:
    https://www.bogotobogo.com/python/python_traversing_directory_tree_recursively_os_walk.php
    '''
    all_names = []
    for root, _, f_names in os.walk(starting_dir):
        for f in f_names:
            this_name = os.path.join(root, f)
            if this_name.endswith(".docx") or this_name.endswith(".pdf"):
                all_names.append(this_name)
    return all_names


def directory_to_cards(rootdir, write_to_file=True):
    '''
    Convert all .docx and .pdf files in a directory into an Anki-importable csv
    of cards. Operates recursively, so that sub-folders within folders are
    located and card-ified too.

    Inputs:
        -rootdir (str): Name of the root folder containing all other subfolders
        and packet files
        -write_to_file (boolean): whether to write out the resulting df to .csv
        or return it in-environment
    Returns (pandas DataFrame): cards    
    '''
    cards_df = pd.DataFrame(columns=['clue', 'answer', 'tags'])

    all_files = get_all_filenames(rootdir)
    print(all_files)
    
    for filename in all_files:
        try:
            this_file_df = file_to_cards(filename, write_to_file=False)
            print(f"Appending cards from {filename}...")
            cards_df = cards_df.append(this_file_df)
        except: #TODO: specify frequent errors that might trigger this
            print(f"\nError: Attempt to cardify {filename} failed.")
            print("Skipping and resuming with next file...\n")
            time.sleep(0.5)

    cards_df = cards_df.drop_duplicates().reset_index(drop=True)

    if write_to_file:
        now = datetime.now().strftime("%Y%-m%d-%H%M%S")
        filepath = f"test_output/folder_clues_{now}.csv"
        print(f"Writing clue cards to {filepath}...")
        write_out(cards_df, filepath)
        print("Write-out complete")
    else:
        print("Here's your dataframe of future cards. Enjoy!")
        return cards_df


if __name__ == '__main__':
    packet_df = directory_to_cards("./test_input", write_to_file=False)
    print(packet_df)
