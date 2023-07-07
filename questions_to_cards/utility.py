import pandas as pd

def write_out(clues, filepath):
    '''
    Write out rows of (clue, answer, tagstring) to an Anki-compatible,
    tab-separated .csv file.
    '''
    clues.loc[:,['clue', 'answer', 'tags']].to_csv(filepath, sep="\t", 
                                                   escapechar="\\", index=False)
