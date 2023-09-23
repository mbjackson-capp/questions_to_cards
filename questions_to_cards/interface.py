import pandas as pd
from qbreader import query
from backup_to_cards import intake
import re

ALL_CATEGORIES = {
    'Literature': ('American Literature', 'British Literature', 
                    'Classical Literature', 'European Literature', 
                    'World Literature', 'Other Literature'),
    'History': ('American History', 'Ancient History', 
                'European History', 'World History', 'Other History'),
    'Science': ('Biology', 'Chemistry', 'Physics', 'Math', 'Other Science'),
    'Fine Arts': ('Visual Fine Arts', 'Auditory Fine Arts', 'Other Fine Arts'),
    'Religion': ('Religion'),
    'Mythology': ('Mythology'),
    'Philosophy': ('Philosophy'),
    'Social Science': ('Social Science'),
    'Current Events': ('Current Events'),
    'Geography': ('Geography'),
    'Other Academic': ('Other Academic'),
    'Trash': ('Trash')
}

# This will be broken for Science vs Social Science
LETTER_TO_CAT = {key[0]: key for key in ALL_CATEGORIES}
LETTER_TO_CAT['S'] = "Science"
LETTER_TO_CAT['A'] = "Fine Arts"

def command_line_app():
    '''
    Run a command line interface that gets questions and turns them into cards.
    '''
    source = input(f"Where would you like to get questions from?\n" +
                   f"Type 'file' for file, 'folder' for folder, 'backup' for QBReader backup JSONs," +
                   f"'db' for API call, or 'csv' for a preexisting set of cards data.")
    print(f"You typed {source}")

    if source in ["file", "folder", "csv"]:
        print("This is where you would type the filepath from your current directory.")
        print("However, this option isn't supported yet. Thank you for your patience!")

    elif source in ['db', 'backup']:
        qtype_raw = input("What question type would you like to search for?\n" +
                          "Type 'tossup' for tossups only 'bonus' for bonuses only, or 'all' for all.")
        qtype = qtype_raw.strip().lower()
        if qtype not in ['tossup', 'bonus']:
            qtype = "all"

        diffs_raw = input(f"What difficulties would you like to include?\n" +
                      f"Type integers from 1 to 10 separated by commas, or a range between two numbers (inclusive)\n" +
                      f"with a hyphen between them. Or press Enter to skip/include all: ")
        VALID_DIFF_RE = r'(([1-9]|10)(\s|,|-))+'
        if diffs_raw == '':
            difficulties = list(range(1,11))
            print("Ignoring difficulty selection. All difficulties will be included")
        elif re.match(VALID_DIFF_RE, diffs_raw) or re.match(r'[1-9]|10', diffs_raw):
            diffs_raw = re.split(' |,', diffs_raw)
            difficulties = set()
            for item in diffs_raw:
                if item == '':
                    continue
                if '-' in item:
                    lb = int(re.sub(r'-.+', '', item))
                    ub = int(re.sub(r'.+-', '', item))
                    if lb > ub: # fix difficulties if they're in the wrong order
                        new_lb = ub
                        ub = lb 
                        lb = new_lb
                    item_range = list(range(lb, ub+1))
                    item_range = [i for i in item_range if (i >= 1 and i <= 10)]
                    difficulties = difficulties.union(item_range)
                elif int(item) >= 1 and int(item) <= 10:
                    difficulties.add(int(item))
            difficulties = sorted(list(difficulties))
            print(f"You selected difficulties: {difficulties}")
        else:
            print("That's not a valid difficulty string")   

        cats_raw = input(f"What categories would you like to include?\n" +
                         f"Type TOP-LEVEL qbreader categories separated by COMMAS.\n" +
                         f"To get all categories, type 'ALL' or just press Enter.")
        cats_raw = re.split(',', cats_raw)
        cats_raw = list({i.strip().lower().capitalize() for i in cats_raw if i != ''})
        categories = set()
        if ("all" in cats_raw or len(cats_raw) == 0):
            print("Getting all categories")
            categories = categories.union({key for key in ALL_CATEGORIES.keys()}) 
        else:
            for cat in cats_raw:
                if cat in ALL_CATEGORIES:
                    categories.add(cat)
                elif cat == 'Rm':
                    categories.add("Religion")
                    categories.add("Mythology")
                elif cat == 'Rmp':
                    categories.add("Religion")
                    categories.add("Mythology")
                    categories.add("Philosophy")
                elif cat[0] == 'S':
                    if len(cat) > 1 and (cat[1] == 'o' or cat[1] == 's'):
                        categories.add("Social Science")
                    else:
                        categories.add("Science")
                # handle "Trash" being called "pc" or "pop culture"
                elif cat[0] == 'P':
                    if len(cat) > 1 and (cat[1] == 'c' or cat[1] == 'o'):
                        categories.add("Trash")
                    else:
                        categories.add("Philosophy")
                elif cat[0] in LETTER_TO_CAT:
                    categories.add(LETTER_TO_CAT[cat[0]])
        categories = sorted(list(categories))
        print(f"You selected categories: {categories}")
        print(f'(Invalid categories were removed)')

        #TODO: subcategories
        CATS_WITH_SUBCATS = ["Literature", "Science", "History", "Fine Arts"]
        for cat in categories:
            if cat in CATS_WITH_SUBCATS:
                print(f"Valid subcategories for {cat}: {ALL_CATEGORIES[cat]}")
                these_subcats = input(f"What subcategories of {cat} do you want?\n" +
                                    "Type valid SUBCATEGORIES separated by COMMAS.\n" +
                                    "To get all subcategories, type 'ALL' or just press Enter.\n" +
                                    f"Valid subcategories for {cat} are: {ALL_CATEGORIES[cat]}")
                print("TODO: add cleaned version of those subcategories you just typed to the list")
        #TODO: searchType
        #TODO: queryString
        #TODO: questionType
        #TODO: setName

        if source == 'db':
            print("Querying QBReader API...")
            api_call = query(difficulties=difficulties, categories=categories)

            tossups = pd.json_normalize(api_call['tossups']['questionArray'])
            bonuses = pd.json_normalize(api_call['bonuses']['questionArray'])

        if source == 'backup':
            #TODO: filter down backup using user input
            tossups, bonuses = intake()

        #Feed result of this function into rest of pipeline from backup_to_cards()
        return tossups, bonuses
    
    else:
        print("Invalid input / input not recognized. Try again with one of the listed options")
        return None, None

if __name__ == '__main__':
    tossups, bonuses = command_line_app()
    print(tossups)
    print(bonuses)