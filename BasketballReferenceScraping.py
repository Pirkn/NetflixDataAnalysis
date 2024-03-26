import selenium.common.exceptions
from selenium import webdriver
from selenium.webdriver.common.by import By
import pandas as pd
from io import StringIO
import time

game_seasons = [2017]
# [2017, 2018, 2019, 2020, 2021, 2022, 2023]
game_months = ['october', 'november']
# ['october', 'november', 'december', 'january', 'february', 'march', 'april', 'may', 'june']
months_dict = {
    'October': '10',
    'November': '11',
    'December': '12',
    'January': '01',
    'February': '02',
    'March': '03',
    'April': '04',
    'May': '05',
    'June': '06',
}

basketball_reference_root = 'https://www.basketball-reference.com'
chrome_options = webdriver.ChromeOptions()
chrome_options.add_experimental_option('detach', True)

driver = webdriver.Chrome(options=chrome_options)
box_scores = {}
keys = []


def add_games_to_boxscores():
    """Adds box score link for every game to dictionary"""
    for season in game_seasons:
        for month in game_months:
            # Update the url
            basketball_reference_url = f'https://www.basketball-reference.com/leagues/NBA_{season}_games-{month}.html'

            # Open url in browser
            driver.get(basketball_reference_url)

            # Find table div which contains games
            try:
                table_div = driver.find_element(By.ID, value='div_schedule')
            except selenium.common.exceptions.NoSuchElementException:
                driver.get(basketball_reference_url)
                table_div = driver.find_element(By.ID, value='div_schedule')

            # Find Anchor tags for box-scores
            anchors = table_div.find_elements(By.CSS_SELECTOR, value='.center a')

            # Get box score link
            key = f'{season}-{month}'
            keys.append(key)
            box_scores[key] = [anchor.get_attribute('href') for anchor in anchors]


add_games_to_boxscores()


def get_stats():
    games = []
    base_cols = None
    for key in keys:
        for i in range(0, len(box_scores[key])):
            # 20 requests for minute
            time.sleep(5)

            # basic & advanced team stats for specific game
            stats = []

            # Go to game box score link
            game_link = box_scores[key][i]
            driver.get(game_link)

            # Get Game Date
            header = driver.find_element(By.CSS_SELECTOR, 'H1').text
            game_day = header.split(',')[1].split(' ')[2]
            game_month = months_dict[header.split(',')[1].split(' ')[1]]
            game_year = header.split(',')[-1]
            game_season = key.split('-')[0]

            # ===== GET LINE SCORES =====
            line_score_table = driver.find_element(By.ID, 'div_line_score').get_attribute('innerHTML')
            line_score_df = pd.read_html(StringIO(line_score_table))[0]

            # Adjust Dataframe
            line_score_df.columns = line_score_df.columns.droplevel()
            line_score_df = line_score_df.rename(columns={'Unnamed: 0_level_1': 'team', 'T': 'total'})
            line_score_df = line_score_df[['team', 'total']]

            # line_score_df.to_csv(
            #    f'Basketball_data/line_scores/{line_score_df["team"][0]}vs{line_score_df["team"][1]}_{key}-{game_day}.csv',
            #    index=False)

            # ===== GET BASIC & ADVANCED STATS =====
            teams = list(line_score_df['team'])
            print(f'Handling {teams[0]} vs {teams[1]}')
            for team in teams:
                advanced_id = f'div_box-{team}-game-advanced'
                basic_id = f'div_box-{team}-game-basic'

                # Find advanced stats table
                advanced_stats_table = driver.find_element(By.ID, advanced_id).get_attribute('innerHTML')
                advanced_stats_df = pd.read_html(StringIO(advanced_stats_table), index_col=0)[0]
                advanced_stats_df = advanced_stats_df.apply(pd.to_numeric, errors='coerce')
                advanced_stats_df.columns = advanced_stats_df.columns.droplevel()

                # Find basic stats table
                basic_stats_table = driver.find_element(By.ID, basic_id).get_attribute('innerHTML')
                basic_stats_df = pd.read_html(StringIO(basic_stats_table), index_col=0)[0]
                basic_stats_df = basic_stats_df.apply(pd.to_numeric, errors='coerce')
                basic_stats_df.columns = basic_stats_df.columns.droplevel()

                # Get total team stats for basic and advanced stats and concat.
                totals_df = pd.concat([basic_stats_df.iloc[-1, :], advanced_stats_df.iloc[-1, :]])
                totals_df.index = totals_df.index.str.lower()

                # Get Max scores for each stat & for each team (individual player)
                maxes_df = pd.concat([basic_stats_df.iloc[:-1, :].max(), advanced_stats_df.iloc[:-1, :].max()])
                maxes_df.index = maxes_df.index.str.lower() + '_max'

                stat = pd.concat([totals_df, maxes_df])

                if base_cols is None:
                    base_cols = list(stat.index.drop_duplicates(keep='first'))
                    base_cols = [b for b in base_cols if "bmp" not in b]

                stat = stat[base_cols]
                stats.append(stat)

            # Concat both stats
            stat_df = pd.concat(stats, axis=1).T

            # Create game df
            game = pd.concat([stat_df, line_score_df], axis=1)
            game['home'] = [0, 1]

            # Create Opponent columns
            game_opp = game.iloc[::-1].reset_index()
            game_opp.columns += '_opp'

            # Merge home + opponent columns
            full_game = pd.concat([game, game_opp], axis=1)

            full_game['season'] = game_season

            full_game['date'] = f'{game_year}-{game_month}-{game_day}'
            full_game['date'] = pd.to_datetime(full_game['date'])

            full_game['won'] = full_game['total'] > full_game['total_opp']

            # for every full game data we have 2 rows, from opponent teams perspective & from home teams perspective
            games.append(full_game)
            #full_game.to_csv(f'Basketball_data/game/teams_{teams[0]}-{teams[1]}_season_{game_season}_date_{game_year}-{game_month}-{game_day}.csv', index=False)

    return games


games = get_stats()
full_df = pd.concat(games, axis=1)
full_df.to_csv(f'Basketball_data/all_game_stats_{game_seasons[0]}-{game_seasons[-1]}.csv')

driver.quit()
