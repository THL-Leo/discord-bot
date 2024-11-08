import discord
from discord.ext import commands, tasks
import asyncio
import sqlite3
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Import the scraping and database functions from the previous script
from job_scraper import scrape_github_jobs, create_database, update_database

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

async def embed_job(job, status):
    embed = discord.Embed(title=job['role'],
                      url=job['application_link'],
                      colour=0x00b0f4,
                      timestamp=datetime.now())

    embed.add_field(name="Company",
                    value=job['company'],
                    inline=True)
    embed.add_field(name="Location",
                    value=job['location'],
                    inline=True)
    embed.add_field(name="ID",
                value=job['id'],
                inline=True)
    embed.add_field(name="Date Posted",
                    value=job['date_posted'],
                    inline=False)

    embed.set_footer(text=status)
    return embed

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    create_database()
    update_jobs.start()

@tasks.loop(hours=24)
async def update_jobs():
    jobs = await scrape_github_jobs()
    update_database(jobs)
    
    # Get new jobs added in the last 24 hours
    conn = sqlite3.connect('jobs.db')
    conn.row_factory = dict_factory
    c = conn.cursor()
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    c.execute("SELECT * FROM jobs WHERE date_posted >= ?", (yesterday,))
    new_jobs = c.fetchall()
    conn.close()
    
    # if new_jobs:
    #     channel = bot.get_channel(int(os.getenv('JOB_CHANNEL_ID')))
    #     await channel.send(f"New job listings ({len(new_jobs)}):")
    #     for job in new_jobs:
    #         await channel.send(
    #             f"Company: {job['company']}\n"
    #             f"Role: {job['role']}\n"
    #             f"Location: {job['location']}\n"
    #             f"Application Link: {job['application_link']}\n"
    #             f"Date Posted: {job['date_posted']}"
    #         )

@bot.command()
async def days(ctx, num_days: int):
    if num_days <= 0:
        await ctx.send("Please provide a positive number of days.")
        return

    conn = sqlite3.connect('jobs.db')
    conn.row_factory = dict_factory
    c = conn.cursor()

    date_threshold = (datetime.now() - timedelta(days=num_days)).strftime("%Y-%m-%d")
    c.execute("""
        SELECT j.*, 
               CASE WHEN ua.user_id IS NOT NULL THEN 'Applied' ELSE 'Not Applied' END as status
        FROM jobs j
        LEFT JOIN user_applications ua ON j.id = ua.job_id AND ua.user_id = ?
        WHERE j.date_posted >= ? 
        AND j.application_link IS NOT NULL 
        AND j.application_link != ''
    """, (ctx.author.id, date_threshold))
    
    recent_jobs = c.fetchall()
    conn.close()

    if recent_jobs:
        await ctx.send(f"Jobs posted in the last {num_days} day(s) ({len(recent_jobs)}):")
        for job in recent_jobs:
            embed = await embed_job(job, job['status'])
            await ctx.send(embed=embed)
    else:
        await ctx.send(f"No new jobs found in the last {num_days} day(s).")

@bot.command()
async def jobs(ctx):
    conn = sqlite3.connect('jobs.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM jobs")
    job_count = c.fetchone()[0]
    conn.close()
    await ctx.send(f"There are currently {job_count} job listings in the database.")

@bot.command()
async def apply(ctx, job_id: int):
    conn = sqlite3.connect('jobs.db')
    c = conn.cursor()
    c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job = c.fetchone()
    
    if job:
        c.execute("INSERT OR IGNORE INTO user_applications (user_id, job_id) VALUES (?, ?)", (ctx.author.id, job_id))
        conn.commit()
        await ctx.send(f"Application recorded for job ID {job_id}.")
    else:
        await ctx.send(f"Job ID {job_id} not found.")
    
    conn.close()

@bot.command()
async def unapply(ctx, job_id: int):
    conn = sqlite3.connect('jobs.db')
    c = conn.cursor()
    c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job = c.fetchone()
    
    if job:
        c.execute("DELETE FROM user_applications WHERE user_id = ? AND job_id = ?", (ctx.author.id, job_id))
        conn.commit()
        await ctx.send(f"Application removed for job ID {job_id}.")
    else:
        await ctx.send(f"Job ID {job_id} not found.")
    
    conn.close()

@bot.command()
async def myapps(ctx):
    conn = sqlite3.connect('jobs.db')
    conn.row_factory = dict_factory
    c = conn.cursor()
    c.execute("""
        SELECT jobs.* FROM jobs
        JOIN user_applications ON jobs.id = user_applications.job_id
        WHERE user_applications.user_id = ?
    """, (ctx.author.id,))
    applications = c.fetchall()
    conn.close()
    
    if applications:
        await ctx.send("Your job applications:")
        for job in applications:
            job_info = \
                f"ID: {job['id']}\n"\
                f"Company: {job['company']}\n"\
                f"Role: {job['role']}\n"\
                f"Location: {job['location']}\n"\
                f"Application Link: {job['application_link']}\n"\
                f"Date Posted: {job['date_posted']}"
            await ctx.send(job_info)
    else:
        await ctx.send("You haven't applied to any jobs yet.")

@bot.command()
async def show(ctx, job_id: int):
    conn = sqlite3.connect('jobs.db')
    conn.row_factory = dict_factory
    c = conn.cursor()
    c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job = c.fetchone()
    conn.close()
    
    if job:
        job_info = \
            f"ID: {job['id']}\n"\
            f"Company: {job['company']}\n"\
            f"Role: {job['role']}\n"\
            f"Location: {job['location']}\n"\
            f"Application Link: {job['application_link']}\n"\
            f"Date Posted: {job['date_posted']}"
        await ctx.send(job_info)
    else:
        await ctx.send(f"Job ID {job_id} not found.")

@bot.command()
async def numjobs(ctx):
    conn = sqlite3.connect('jobs.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM jobs")
    job_count = c.fetchone()[0]
    conn.close()
    await ctx.send(f"There are currently {job_count} job listings in the database.")

bot.run(os.getenv('BOT_TOKEN'))