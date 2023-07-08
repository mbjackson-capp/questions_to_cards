from PyPDF2 import PdfReader
from docx import Document
from datetime import datetime
import re
import pandas as pd
import time

from text_processing import tokenize_and_explode, cleanup
from utility import write_out

SPLIT_RE = re.compile(r"(?=ANSWER:)|" #answer line
                    r"(?<=\>)\s?[0-9]{1,2}\.\s|" #question-starting number
                    r"Tossups |"
                    r"Bonuses |"
                    r"\[.{1,3}]\s?|" #part indicator
                    r"(?:__SPLIT__)")

DOCX_JUNK = r'\s+|<[^>]+>'

def pdf_cardify(
        packet_filepath, 
        diff=None, 
        yr=None, 
        split_up=True, 
        clean_up=True,
        write_to_file=True
        ):
    '''
    Convert a packet of quizbowl questions in PDF format to an Anki-compatible
    csv of clue-level flashcards.
    #TODO: Create a wrapper method to loop through an entire folder of packets

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

    #TODO: SPLIT OFF EVERYTHING BELOW INTO ITS OWN FUNCTION
    #(which pdf and docx input streams can both feed into)

    #TODO: check here if ANSWER: is in the right places, halt or warn user if not

    clue = []
    answer = []
    for idx, segment in enumerate(all_text):
        # alternate clue-answer except for bonus leadins, which "leap ahead" to find 
        # the corresponding answer
        #TODO: create or import a more thorough FTPE_RE for edge cases and old questions
        if 'or 10 points each' in segment:
            clue.append(segment)
            leadin_ans = re.sub('ANSWER: ', '', all_text[idx+2]) #TODO: fix magic number 2
            answer.append(leadin_ans)
        elif 'ANSWER: ' in segment:
            segment = re.sub('ANSWER: ', '', segment)
            answer.append(segment)
        else:
            clue.append(segment)

    packet_df = pd.DataFrame({'clue':clue,
                            'answer':answer})

    if split_up:
        packet_df = tokenize_and_explode(packet_df)
        if clean_up:
            packet_df = cleanup(packet_df)

    packet_df.loc[:,'tags'] = ''
    if diff is not None:
        packet_df.loc[:,'tags'] += f"diff::{diff} "
    if yr is not None:
        packet_df.loc[:,'tags'] += f"yr::{yr} "
    packet_df.loc[:,'tags'] = packet_df.loc[:,'tags'].str.strip()

    if write_to_file:
        now = datetime.now().strftime("%Y%-m%d-%H%M%S")
        filepath = f"test_output/packet_clues_{now}.csv"
        print(f"Writing clue cards to {filepath}...")
        write_out(packet_df, filepath)
        print("Write-out complete")
    else:
        print("Here is your dataframe. Enjoy!")
        return packet_df

def docx_to_cards(packet_filepath):
    '''
    Convert a .docx file into cards. 
    Inspired by qbreader doc-to-txt.py, by Geoffrey Wu
    '''
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
    

    #TODO: fix SPLIT_RE so it doesn't produce a bunch of blanks

    return all_text

if __name__ == '__main__':
    choice = input("Cardify the PDF? Or test the .docx? : ")
    if 'pdf' in choice.lower():
        packet_df = pdf_cardify(
            'test_input/Packet A.pdf', 
            diff=8, 
            yr=2022, 
            split_up=True)
        print(packet_df)
    elif 'doc' in choice.lower():
        output = docx_to_cards('test_input/Packet 1.docx')
        for item in output:
            print(item)
            print('\n')
            time.sleep(0.5)
        print(len(output))
