from PyPDF2 import PdfReader
from docx import Document
from datetime import datetime
import re
import pandas as pd
import os

from text_processing import tokenize_and_explode, cleanup
from utility import write_out

#TODO: put non-match group in proper place so output of re.split() doesn't
#produce a bunch of blanks
SPLIT_RE = re.compile(r"(?=ANSWER:)|" #answer line
                    r"(?<=\>)\s?[0-9]{1,2}\.\s|" #question-starting number
                    r"Tossups |"
                    r"Bonuses |"
                    r"\[[10emh]{1,3}]\s?|" #part indicator
                    r"(?:__SPLIT__)")

#TODO: figure out a better way to deal with "Bonuses" in BHSU packet 1
DOCX_JUNK = r'\s+|<[^>]+>|Bonuses'


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
        write_to_file=True,
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
        if segment == 'Bonuses':
            continue
        elif 'or 10 points each' in segment:
            clues.append(segment)
            leadin_ans = re.sub('ANSWER: ', '', all_text[idx+2]) #TODO: fix magic number 2
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

    #TODO: maybe reset_index() here; final index is larger than df length

    if write_to_file:
        now = datetime.now().strftime("%Y%-m%d-%H%M%S")
        filepath = f"test_output/packet_clues_{now}.csv"
        print(f"Writing clue cards to {filepath}...")
        write_out(packet_df, filepath)
        print("Write-out complete")
    else:
        return packet_df

def folder_to_cards(folder, write_out=True):
    '''
    Convert all .docx and .pdf files in a folder into an Anki-importable csv
    of cards. 
    Inputs:
        -folder (str): Name of the directory to be carded
        -write_out (boolean): whether to write out the resulting df to .csv
        or return it in-environment
    Returns (pandas DataFrame): cards
    '''
    cards_df = pd.DataFrame(columns=['clue', 'answer', 'tags'])

    for filename in os.listdir(folder):
        full_name = folder + '/' + filename
        print(os.path.abspath(full_name))
        if '.pdf' in filename:
            this_file_text = pdf_to_text(full_name)
        elif '.docx' in filename:
            this_file_text = docx_to_text(full_name)

        print(f"Appending cards from {filename}...")
        cards_df.append(text_to_cards(this_file_text, write_to_file=False))

    if write_out:
        now = datetime.now().strftime("%Y%-m%d-%H%M%S")
        filepath = f"test_output/folder_clues_{now}.csv"
        print(f"Writing clue cards to {filepath}...")
        write_out(cards_df, filepath)
        print("Write-out complete")
    else:
        print("Here's your df")
        return cards_df



if __name__ == '__main__':
    choice = input("Cardify the PDF? Or the .docx? : ")
    if 'pdf' in choice.lower():
        packet_text = pdf_to_text('test_input/Packet A.pdf')
    elif 'doc' in choice.lower():
        packet_text = docx_to_text('test_input/Packet 1.docx')
    packet_df = text_to_cards(packet_text, write_to_file=False)
    print(packet_df)
