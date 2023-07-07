from PyPDF2 import PdfReader
import re
import pandas as pd
from backup_to_cards import tokenize_and_explode, clean_clue_text, clean_answer_text

def cardify(packet_filepath, diff=None, yr=None, split_up=False):
    '''
    Convert a packet of quizbowl questions in PDF format to an Anki-compatible
    csv of clue-level flashcards.
    #TODO: Add support for .docx
    #TODO: add clue and answer text processing from other file
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

    SPLIT_RE = re.compile("(?=ANSWER:)|" #answer line
                        "(?<=\>)\s?[0-9]{1,2}\.\s|" #question-starting number
                        "Tossups |"
                        "Bonuses |"
                        "\[.{1,3}]\s?") #part indicator

    all_text = re.sub('\n', ' ', all_text) #remove spurious newlines
    all_text = re.sub('^.+Tossups', '', all_text) #remove authorship credits from top
    all_text = re.split(SPLIT_RE, all_text)

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
        #TODO: clue and answer text processing

    packet_df.loc[:,'tags'] = ''
    if diff is not None:
        packet_df.loc[:,'tags'] += f"diff::{diff} "
    if yr is not None:
        packet_df.loc[:,'tags'] += f"yr::{yr} "
    packet_df.loc[:,'tags'] = packet_df.loc[:,'tags'].str.strip()

    return packet_df

if __name__ == '__main__':
    packet_df = cardify('test_input/Packet A.pdf', diff=8, yr=2022, split_up=True)
    print(packet_df)
