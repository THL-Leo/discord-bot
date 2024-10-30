# Job Board Bot

I am an avid discord user and it is also the job application season. I wanted some form of tracking what jobs I have applied to but without making a messy excel file or a fancy Notion database. This bot utilizes Playwright to scrape the README.md job board on the simplify github repo. It then connects to my discord server so I can get a list of newly updates jobs in the channel. I can update the status of the job application as well.

## Technology Used

- **Discord.py**: Used for connecting my code to the bot on Discord using Discord's API and tokens.
- **Playwright**: Utilized for fast and efficient web scraping.
- **SQLite3**: A light weight file based database language perfect for something this small. It is fast and follows conventional SQL query languages.