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



tqdm.pandas()

NUM_BONUS_PARTS = 3

COLUMNS_TO_KEEP = ['clue', 'answer', 'subcategory', 'category', 'type', 
                   'difficulty', 'setName', 'setYear']

BRACKET_RE = r'<[^>]+>'
DUMB_QUOTE_RE = re.compile('(?:“|\")([^\"”]+)(?:\"|”)')

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


def my_split(qtext):
    '''
    Use a regex split questions at the clue (standalone sentence) level.

    Inputs:
        -qtext (str): The tossup or bonus part to be split up
    Returns (lst): A list of the clue-sentences in the tossup or bonus part,
    to be converted later into one card apiece 
    '''
    #PRE-PROCESSING 

    qtext = re.sub(r'…', '...', qtext)

    #replace dumb quotes with smart quotes
    qtext = re.sub(DUMB_QUOTE_RE, r'“\1”', qtext)

    #replace double apostrophes on one end of a quote with dumb quotes
    #e.g. “The Windhover''
    #but beware things like D'' layer or 4'33''
    qtext = re.sub(r'\'\'', '”', qtext)

    #prevent splitting on common titles
    ABBREVS_RE = r'(“|\s)(Mr|Mrs|Ms|Mx|Messrs|Dr|Prof|Rev|Lt|Col|Gen|Gov|No|St|Ste|Mme|Mlle|v|vs|Blvd|Op|Mt|Ft)\.'
    qtext = re.sub(ABBREVS_RE, r'\1\2_DOT_', qtext)

    #fix order of period-close quote so other REs work better
    WRONG_ENDQUOTE_RE = r'(?<=[a-z])\.“(?= [A-Z])'
    qtext = re.sub(WRONG_ENDQUOTE_RE, '.”', qtext)

    #prevent from splitting quotations
    PERIOD_IN_SMART_QUOTES_RE = r'(?<=“)([^”]+)\.([^”]+)(?=”)'
    #this operation only replaces one so you need to while loop it
    while qtext != re.sub(PERIOD_IN_SMART_QUOTES_RE, r'\1_DOT_\2', qtext):
        qtext = re.sub(PERIOD_IN_SMART_QUOTES_RE, r'\1_DOT_\2', qtext)
        
    #Should be obviated by replacement of dumb quotes
    PERIOD_IN_DUMB_QUOTES_RE = r'(\"[^\.\"]+)\.( [^\.\"]+(\.|\?|\!|)\")'
    qtext = re.sub(PERIOD_IN_DUMB_QUOTES_RE, r'\1_DOT_\2', qtext)

    #remove pronunciation guides where possible
    PRONUNC_GUIDE_RE = r'\s(\[“[^\[\]]+”\]|\(“[^\(\)]+”\)|\(pron[^\)]+\)|\[pron[^\]]+\])'
    qtext = re.sub(PRONUNC_GUIDE_RE, '', qtext)

    #remove power marks
    POWER_MARK_RE = r'\((\*|\+){1,2}\)\s?'
    qtext = re.sub(POWER_MARK_RE, '', qtext)

    #TODO: improve documentation for this monster regex
    #Default behavior: split at end-of-sentence periods that aren't within quotation marks
    TEST_BEST_SPLIT_RE = re.compile(r'(?<=[^ A-Z]\.\s)' #prevent splitting on initials or ellipses
                                    r'(?=[\s0-9A-Z“])|' #look ahead to see if next sentence
                                    #starts with number, capital letter, or left quotation mark
                                    r'(?<=(?:\?|\.|\!)(?:”|\")\s)(?=[^a-z])|' # "core"
                                    r'(?<=[A-Z]{2}\. )|' #deal with sentences that end with
                                    #an initialism like 'CO' or 'DRNA'
                                    r'(?<=\.”|\.\")(?=[0-9A-Z])') #handle sentences with no space;
                                    #e.g. 2023 ACF Regionals 'House of Usher' tossup

    return re.split(TEST_BEST_SPLIT_RE, qtext)



def tokenize_and_explode(clues):
    '''
    Split each tossup and/or bonus part at the sentence level and make each
    sentence its own row, leaving all else intact. The effect of this is to
    create one card (row) for each clue of a question.

    Inputs:
        -clues (pandas DataFrame)
    Returns (pandas DataFrame): modified DataFrame with one row per clue
    (TODO: figure out how to do a pandas inplace=True)
    '''
    clues.loc[:,'clue'] = clues.loc[:,'clue'].progress_apply(lambda x: my_split(x))

    clues_exploded = clues.explode(["clue"],ignore_index=True)

    #TODO: isolate the tossup giveaways and give them type 'tossup_giveaway'

    return clues_exploded

def cleanup(clues):
    '''
    Cleans all clues and answers IN THE WHOLE DATAFRAME, calling helper functions
    as needed.

    Inputs:
        -clues (pandas DataFrame)
        -old_version (boolean): determines whether modifications to clues are
        made at the dataframe level through .loc selectors (old) or by applying a 
        vectorized function to do all replacements at clue level (new)
    Returns (DataFrame): as if modified in-place

    TODO: add a 'verbose' mode 
    TODO: Split into helpers for each kind of cleanup
    '''
    print("Removing unwanted rows (e.g. duplicates, obvious non-clues)...")
    clues = clues.drop_duplicates('clue')

    #TODO: use .pattern attribute to improve REs?
    ANSWER_FOLLOWING_RE = re.compile(r'(Answer|Identify|Respond appropriately to) '
                                     r'(th(e|is)|these|some) '
                                     r'(following|questions)',
                                     re.IGNORECASE)
    clues = clues.loc[(~clues.loc[:,'clue'].str.contains(ANSWER_FOLLOWING_RE, regex=True)), :]

    #Remove non-clue bonus leadins

    #TODO: fix this to be an re_compile that also uses FTP_RE
    NO_CLUE_BONUS_LEADIN_RE = re.compile(r'(identify|name|give) '
                                         r'(these|three|some).+'
                                         r'(for 10 points each|ftpe)',
                                         re.IGNORECASE)
    clues = clues.loc[(~clues.loc[:,'clue'].str.contains(NO_CLUE_BONUS_LEADIN_RE, regex=True)), :]

    clues = clues.loc[~((clues.loc[:,'clue'].str.contains('some stuff')) & 
               (clues.loc[:,'type'] == 'bonus_leadin')), :]

    print("Removing 30-20-10s...")
    clues = clues.loc[(~clues.loc[:,'clue'].str.contains('30-20-10')), :]

    print("Cleaning clue text...")
    clues.loc[:,'clue'] = clues.loc[:,'clue'].progress_apply(lambda x: 
                                                             clean_clue_text(x))

    #remove extremely short clues, including:
    # - standalone numbers/letters/initials
    # - "pencil and paper ready"
    # - "you have n seconds"
    print("Removing extremely short clues...")
    clues = clues.loc[(clues.loc[:,'clue'].str.len() > 25), :]

    print("Cleaning answer line text...")
    clues.loc[:,'answer'] = clues.loc[:,'answer'].progress_apply(lambda x: clean_answer_text(x))

    return clues

def clean_clue_text(qtext):
    '''
    Function to be applied ON A SINGLE CLUE to take advantage of pandas 
    vectorization / prevent multiple passes through when just one will do.
    Should be done after splitting the questions into clues, not before

    This used to be written at the df level with selectors like:
        clues.loc[:,'clue'] = clues.loc[:,'clue'].str.replace('_DOT_', '.')
    but now it's not.

    Inputs:
        qtext (str): content of a single cell in the 'clue' column
    Returns (str): that string, with unwanted elements removed and text fixed
    '''
    #revert _DOT_s back
    qtext = re.sub('_DOT_', '.', qtext)

    #remove HTML-y tags
    BRACKET_RE = r'<[^>]+>'
    qtext = re.sub(BRACKET_RE, '', qtext) 

    #edge case: a bonus where "The FTP" is an actual organization in the clue
    qtext = re.sub('The FTP', 'The F.T.P.', qtext)
    #get rid of ftp/ftpe throughout
    FTP_RE = re.compile('(, |–{1,2}|—)?(for (5|five|10|ten|15|fifteen|the stated number of) po?i(nt|tn)s?(,)?( each| ecah)?(,|:)?)|f(t|f)(sno)?p(e)?(,|:|\.|–{1,2}|—)?', 
                        re.IGNORECASE)
    qtext = re.sub(FTP_RE, r'\1', qtext)

    #get rid of stray point markers (beware that sometimes these result from mis-parsing "A.")
    POINT_MARK_RE = r'\[(5|10|)\]\s' #will also remove empty brackets
    qtext = re.sub(POINT_MARK_RE, '', qtext)

    #remove "description acceptable" phrase (does not handle "warning/note to players")
    DESC_ACC_RE = re.compile('(a )?(name or )?(a )?(general )?description\s(is|)acceptable(\.|:|)\s?',
                              re.IGNORECASE)
    qtext = re.sub(DESC_ACC_RE, '', qtext)

    #remove "warning"s and "notes"
    WARNING_RE = re.compile('^(Note( to (teams|players?|reader|moderator)|)|Moderator note|(Content |)warning):?',
                            re.IGNORECASE)
    qtext = re.sub(WARNING_RE, '', qtext)

    READ_SLOW_RE = r'(?<![A-Z])read[^“y]+(slowly|carefully)' 
    #the y in the non brackets is a kludge to save stuff inside "(read slowly)...
    # (end read slowly) tags from getting eaten
    qtext = re.sub(READ_SLOW_RE, '', qtext)
    
    #remove mod instructions to emphasize
    qtext = re.sub('(\[|\()emphasize(\]|\))', '', qtext)

    qtext = re.sub('from clues', '', qtext)

    #TODO: remove dashes around the missing "--for 10 points--"
    #DASH_RE = r'(—{1,2}|–{2,4}|--\s?--)s?what'
    #qtext = re.sub(DASH_RE, ' what', qtext)

    #Remove "n answers required / specific term required / genre and composer required etc."
    #inspecting the data, it looks like this is a good length threshold
    REQD_LEN_THRESHOLD = 70
    if len(qtext) < REQD_LEN_THRESHOLD and bool(re.search(r'required\.', qtext)):
        qtext = ''

    #remove remaining "...is/are acceptable" clues
    #inspecting the data, it looks like the shortest real clue with 'acceptable'
    #in it is of length 86
    #TODO: remove about fifteen 'false positive' non-clues above this length
    DESC_ACC_THRESHOLD = 86
    if len(qtext) < DESC_ACC_THRESHOLD and bool(re.search(r'acceptable\.', qtext)):
        qtext = ''

    #capitalize clue-initial consonant
    qtext = qtext.strip()
    try:
        qtext = qtext[0].upper() + qtext[1:]
    except IndexError: #clues that are now of length 0
        pass

    return qtext

def clean_answer_text(atext):
    '''
    Function to be applied ON A SINGLE ANSWER LINE to take advantage of pandas 
    vectorization / prevent multiple passes through when just one will do.
    Should be done after splitting the questions into clues, not before

    This used to be written at the df level with selectors like:
        clues.loc[:,'answer'] = clues.loc[:,'answer'].str.replace('_DOT_', '.')
    but now it's not.

    Inputs:
        atext (str): content of a single cell in the 'answer' column
    Returns (str): that string, with unwanted elements removed and text fixed
    '''
    ANS_MISSING = "THE ANSWER TO THIS CLUE WAS MISSING ON QBREADER. LOOK IT UP"
    if len(atext) == 0 or atext == "[MISSING]":
        atext = ANS_MISSING

    #Turn dumb quotes into smart quotes
    atext = re.sub(DUMB_QUOTE_RE, r'“\1”', atext)

    #get rid of angle-brackets, e.g. author credits, html tags
    atext = re.sub(BRACKET_RE, '', atext)

    #get rid of improperly rendered angle brackets
    LTGT_RE = re.compile('&lt;.+&gt;')
    atext = re.sub(LTGT_RE, '', atext)

    DO_NOT_REVEAL_RE = re.compile('(,|) but do not( otherwise|) reveal(,|)', re.IGNORECASE)
    atext = re.sub(DO_NOT_REVEAL_RE, '', atext)

    REJECT_RE = re.compile('(; |, |)(do not (accept|prompt|take)|reject)[^\]\)]+(?=\]|\))',
                           re.IGNORECASE)
    atext = re.sub(REJECT_RE, '', atext)

    #sweep out empty brackets, e.g. where reject instructions used to be
    EMPTY_BRACKET_RE = r'\[\s?\]|\(\s?\)'
    atext = re.sub(EMPTY_BRACKET_RE, '', atext)

    #TODO: "note:/Editors' note: / Ed’s note:" / parenthetical or bracketed statements

    return atext.strip()

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
    
def write_out(clues, filepath):
    '''
    Write out rows of (clue, answer, tagstring) to an Anki-compatible,
    tab-separated .csv file.
    '''
    clues.loc[:,['clue', 'answer', 'tags']].to_csv(filepath, sep="\t", 
                                                   escapechar="\\", index=False)

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
    run()