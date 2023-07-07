import pandas as pd
import numpy as np
import re
from tqdm import tqdm

tqdm.pandas()

BRACKET_RE = r'<[^>]+>'
DUMB_QUOTE_RE = re.compile('(?:“|\")([^\"”]+)(?:\"|”)')

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

    if type in clues.columns:
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