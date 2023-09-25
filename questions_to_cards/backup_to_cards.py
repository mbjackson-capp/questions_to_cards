###############################################################################
# QUESTIONS TO FLASHCARDS
# By: Matt Jackson (Github: mbjackson-capp)
# Version 0.0
# May 2023
# Special thanks to: Geoffrey Wu
##############################################################################

import pandas as pd
import numpy as np
import re
import os
from datetime import datetime
from tqdm import tqdm
from text_processing import tokenize_and_explode, cleanup, my_split, clean_clue_text, clean_answer_text
from utility import write_out
from similarity import remove_redundancies

tqdm.pandas()

NUM_BONUS_PARTS = 3

COLUMNS_TO_KEEP = ['clue', 'answer', 'subcategory', 'category', 'type', 
                   'difficulty', 'setName', 'setYear']

def intake():
    '''Read in tossups.json and bonuses.json'''

    assert ('tossups.json' in os.listdir() and
            'bonuses.json' in os.listdir()), "You don't have the qbreader backup files in this directory!"
    
    tossups = pd.read_json("tossups.json",lines=True)
    tossups.rename(columns={'question':'clue'}, inplace=True)

    bonuses = pd.read_json("bonuses.json",lines=True)

    return tossups, bonuses


def max_tossup_length(tossups):
    '''Find the length of the longest tossup in the database. This is used to
    set pd.options.display.max_colwidth, which needs to be at least as wide
    as the tossup to allow tokenizer to access full question text.
    
    Inputs:
        -tossups (DataFrame): tossups DataFrame
    Returns (int): longest tossup length'''

    assert 'clue' in tossups.columns

    curr_max = 0
    for string in tossups.loc[:,'clue']:
        if len(string) > curr_max:
            curr_max = len(string) 
    return curr_max
  

def reformat(bonuses):
    '''
    Changes the bonuses table to a format where each component of the bonus
    (leadin, part 1, part 2, part 3) has its own row with a clue and its
    corresponding answer.
    #TODO: consider making more "panda-ic" with .stack()
    Inputs:
        -bonuses (pandas DataFrame)
    Returns (pandas DataFrame): transformed table
    '''
    #Filter out bonuses with the wrong number of parts. 
    #TODO: Generalize this to handle bonuses with a number of parts other than 3 (min is 0, max is 6)
    #https://intellipaat.com/community/31700/pythonic-way-for-calculating-length-of-lists-in-pandas-dataframe-column
    parts_clean_filter = bonuses.loc[:,'parts'].str.len() == NUM_BONUS_PARTS
    answers_clean_filter = bonuses.loc[:,'answers'].str.len() == NUM_BONUS_PARTS

    len_before = len(bonuses)
    bonuses = bonuses.loc[parts_clean_filter & answers_clean_filter,:]
    print(f"{len_before - len(bonuses)} rows eliminated for having non-standard number of parts or answers")

    #make columns ['part1', 'answer1', 'part2', 'answer2', 'part3', 'answer3']
    for num in range(NUM_BONUS_PARTS):
        bonuses.loc[:,'part' + str(num+1)] = [i[num] for i in bonuses.loc[:,'parts']]
        bonuses.loc[:,'answer' + str(num+1)] = [i[num] for i in bonuses.loc[:,'answers']]

    #Get a dataframe whose columns are just "Clue" - "Answer", stacking parts atop
    #each other like this for each bonus:
        #leadin : answer1
        #part1  : answer1
        #part2  : answer2
        #part3  : answer3
    #rename is needed for pd.concat to stack properly
    clue_answer_pairs = pd.concat(
        (bonuses.loc[:,['leadin','answer1']].copy().rename(columns={'leadin':'clue', 'answer1':'answer'}),
        bonuses.loc[:,['part1','answer1']].copy().rename(columns={'part1':'clue', 'answer1':'answer'}),
        bonuses.loc[:,['part2','answer2']].copy().rename(columns={'part2':'clue', 'answer2':'answer'}),
        bonuses.loc[:,['part3','answer3']].copy().rename(columns={'part3':'clue', 'answer3':'answer'})),
                                axis=0)

    bonus_parts = pd.concat([bonuses.copy()] * 4, axis=0)

    bonus_parts.reset_index(inplace=True, drop=True)
    clue_answer_pairs.reset_index(inplace=True, drop=True)

    bonus_parts = pd.concat((bonus_parts,clue_answer_pairs),axis=1).loc[:,COLUMNS_TO_KEEP]

    #assign the first quarter of the rows a type of 'bonus_leadin' and it should work
    bonus_parts.loc[0:len(bonus_parts) // 4 - 1, 'type'] = 'bonus_leadin'
    
    return bonus_parts


def put_together(tossups, bonus_parts):
    '''
    Combines the tossup df and the bonuses df.
    Don't call this until bonus parts are reformatted!
    '''
    assert list(bonus_parts.columns) == COLUMNS_TO_KEEP, "Bonus parts are not properly processed yet!"

    tossups = tossups.rename(columns={'question':'clue'}).loc[:,COLUMNS_TO_KEEP]

    clues = pd.concat((tossups, bonus_parts), axis=0)
    clues.reset_index(drop=True, inplace=True)

    return clues


def mongo_fix(obj):
    '''Turns a MongoDB representation of an integer from the QBReader database
    into an integer. Uses 0 for missing values.
    
    Inputs:
        -obj (dict): the {$...} JSON object
    Returns (int): Integer representation'''

    if type(obj) == int:
        return obj

    strobj = str(obj)
    try:
        fixed_obj = int(re.search(r"[0-9]{1,4}", strobj).group(0))
    except AttributeError:
        fixed_obj = 0
    return fixed_obj


def tagstring(row):
    '''
    Creates a string that Anki can read in as tags for a card.
    TODO: consider using re.sub and avoiding type conversion for speedup
    Input: 
        -row (pandas row-like object): single row of clues DataFrame
    Returns (str): something like "cat::Science::Biology diff::8 yr::2012 type::bonus"
    which Anki turns into hierarchical tags
    '''
    #Anki tags cannot have spaces in their names; space is interpreted
    try:
        cat = row['category'].replace(' ', '')
    except: #category or subcategory is "nan"
        cat = "NA"
    try:
        subcat = row['subcategory'].replace(' ', '')
    except:
        subcat = "NA"
    diff = row['difficulty']
    yr = row['setYear']
    type = row['type']
    length = row['len']

    tag_str = f"cat::{cat}::{subcat} diff::{diff} yr::{yr} type::{type} length::{length}"
    #reduce redundant subcats like "Religion::Religion" to just cat
    CAT_RE = re.compile(r"(Religion|Mythology|Philosophy|Social Science|Geography|Current Events|Trash)::\1")
    tag_str = re.sub(CAT_RE, r"\1", tag_str)
    return tag_str

    #TODO: a tag for if the clue has no pronoun, to flag as a possible non-clue
    #PRONOUN_RE = re.compile('((?<=\s)(he|him|his|she|her|hers|it|its|it\'s|it’s|they|them|their|theirs|they\'re|they’re)|^(he|him|his|she|her|hers|it|its|it\'s|it’s|they|them|their|theirs|they\'re|they’re)|(this|these|that|those))(\s|\.|\?|’|\!)',
    # re.IGNORECASE)
    

###TESTS###  

def single_question_test(qtext, atext=''):
    '''
    Tests the tokenization and editing at a question level.

    Inputs:
        -qtext (str): Single tossup or bonus part (leadin, part 1, part 2, or part 3)
        -atext (str): the corresponding answer line
    Returns (tuple of lists): all clues for the question, plus the answer line,
    as they will appear on cards
    '''
    if qtext is None:
        qtext = ''
    if atext is None:
        atext = ''

    ANSWER_FOLLOWING_RE = re.compile('(Answer|Identify|Respond appropriately to) (th(e|is)|these|some) (following|questions)',
                                     re.IGNORECASE)
    
    NO_CLUE_BONUS_LEADIN_RE = re.compile('(identify|name|give) (these|three|some).+(for 10 points each|ftpe)',
                                         re.IGNORECASE)

    qlist = my_split(qtext)
    qlist = [str for str in qlist if not re.search(ANSWER_FOLLOWING_RE, str)]
    qlist = [str for str in qlist if not re.search(NO_CLUE_BONUS_LEADIN_RE, str)]
    qlist = [clean_clue_text(clue) for clue in qlist]
    qlist = [clue for clue in qlist if len(clue) > 25]

    alist = [clean_answer_text(atext)]

    return qlist, alist

def answer_lines_test(write_to_file=True):
    '''
    Isolate effect of text changes on answer lines without running through
    the whole pipeline rigamarole.
    Just uses tossups.csv for simplicity.
    '''
    tossups, _ = intake()

    tossups.loc[:,'answer'] = tossups.loc[:,'answer'].progress_apply(lambda x: 
                                                                     clean_answer_text(x))
    
    if write_to_file:
        now = datetime.now().strftime("%Y%-m%d-%H%M%S")
        filepath = f"answertest_{now}.csv"
        print(f"Writing answer lines to {filepath}...")
        tossups.loc[:,['answer']].to_csv(filepath, sep="\t", 
                                                    escapechar="\\", index=False)
    else:
        return tossups.loc[:,'answer']


def intake_test(tokenized=True, add_len_col=True, drop_repeats=True, clean_up=True):
    '''
    Simplified version of run(). For use in testing environments such as iPython 
    '''
    print("Reading in tossups and bonuses...")
    tossups, bonuses = intake(); 
    print("Putting tossups and bonuses in single sheet:")
    clues = put_together(tossups, reformat(bonuses))
    if tokenized:
        print("Splitting questions into clues...")
        clues = tokenize_and_explode(clues)
    
    clues.loc[:,'setYear'] = clues.loc[:,'setYear'].apply(lambda x: mongo_fix(x))
    clues.loc[:,'difficulty'] = clues.loc[:,'difficulty'].apply(lambda x: mongo_fix(x))

    if add_len_col:
        print("Adding a column for clue length...")
        clues.loc[:,'len'] = clues.loc[:,'clue'].str.len()

    if drop_repeats:
        print("Eliminating repeat clues...") #removes about 103536 rows
        clues.drop_duplicates('clue', inplace=True)

    if clean_up:
        clues = cleanup(clues)

    print("Done")
    return clues

def run(normalize_len=True, write_to_file=True):
    '''
    Runs the whole data transformation pipeline to turn QBReader database backups
    into a file that is ready to import into Anki as flashcards.
    #TODO: Add some parameters to restrict to subsets of the data
    '''
    print("Reading in tossups and bonuses from QBReader backup file...")
    tossups, bonuses = intake()
    #pd.options.display.max_colwidth = max_tossup_length(tossups)

    print("Splitting bonuses into parts...")
    bonuses = reformat(bonuses)

    print("Putting tosusps and bonuses into single DataFrame...")
    clues = put_together(tossups, bonuses)

    print("Splitting questions and parts into individual clues...")
    clues = tokenize_and_explode(clues)

    print("Fixing MongoDB junk in columns...")
    clues.loc[:,'setYear'] = clues.loc[:,'setYear'].apply(lambda x: mongo_fix(x))
    clues.loc[:,'difficulty'] = clues.loc[:,'difficulty'].apply(lambda x: mongo_fix(x))

    print("Adding a column for clue length...")
    clues.loc[:,'len'] = clues.loc[:,'clue'].str.len()

    print("Eliminating repeat clues...") #removes about 103536 rows
    clues.drop_duplicates('clue', inplace=True)

    print("Cleaning up remaining clues...")
    clues = cleanup(clues)

    #clean length here
    if normalize_len:
        print("Normalizing length column...")
        clues.loc[:,'len'] = clues.loc[:,'clue'].str.len() #recalculate
        LEN_MEAN = clues.loc[:,'len'].agg(np.mean)
        print(f"Mean clue length: {LEN_MEAN}")
        LEN_STD = clues.loc[:,'len'].agg(np.std)
        print(f"Clue length standard deviation: {LEN_STD}")
        clues.loc[:,'len'] = (clues.loc[:,'len'] - LEN_MEAN) / LEN_STD
        clues.loc[:,'len'] = clues.loc[:,'len'].apply(np.floor).astype(int)
        #clues 7+ stdev above mean can be lumped together
        clues.loc[:,'len'] = clues.loc[:,'len'].apply(lambda x: min(7, x))

    print("Generating Anki tags...")
    clues['tags'] = clues.progress_apply(lambda x: tagstring(x), axis=1)

    print("Run redundant clue removal algorithm? Type 'yes' to confirm.")
    rr_input = input("WARNING: This will take several hours.")
    if rr_input == 'yes':
        rr_input = input("Are you sure?? Type 'yes' again to confirm.")
        if rr_input == 'yes':
            print("Do you want to lemmatize words in clues? Type 'yes' to confirm.")
            lemma_input = input("WARNING: This will add as much as several hours to runtime.")
            lemma_choice = (lemma_input == 'yes')
            clues = remove_redundancies(clues, lemmatize=lemma_choice)

    if write_to_file:
        now = datetime.now().strftime("%Y%-m%d-%H%M%S")
        filepath = f"clues_{now}.csv"
        print(f"Writing clue cards to {filepath}...")
        write_out(clues, filepath)
        print(f"Writeout complete! Now, open Anki and go to File->Import->{filepath}.")
        print("Enjoy carding!")
    else:
        print("Enjoy your dataframe!")
    
    return clues

if __name__ == "__main__":
    run(write_to_file=False)