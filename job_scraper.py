import asyncio
from playwright.async_api import async_playwright
import re
import sqlite3
from datetime import datetime, timedelta

def parse_date_posted(date_str, current_year=2024):
    months = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    
    month, day = date_str.split()
    month_num = months[month[:3]]
    day = int(day)
    
    # Determine the year
    now = datetime.now()
    if month_num > now.month or (month_num == now.month and day > now.day):
        year = current_year - 1
    else:
        year = current_year
    
    # Create the datetime object
    date_posted = datetime(year, month_num, day)
    
    return date_posted.strftime('%Y-%m-%d %H:%M:%S')

async def scrape_github_jobs():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://github.com/SimplifyJobs/New-Grad-Positions")
        
        # Wait for the table to load
        await page.wait_for_selector('table')
        
        # Extract the table content
        table_content = await page.evaluate('''() => {
            const table = document.querySelector('table');
            return table.outerHTML;
        }''')
        
        await browser.close()
        
        # Parse the table content
        rows = re.findall(r'<tr class="react-directory-row.*?</tr>', table_content, re.DOTALL)
        jobs = []
        
        for row in rows:
            # Extract file name (which is the README.md in this case)
            name_match = re.search(r'title="([^"]+)".*?href="([^"]+)"', row)
            if name_match and name_match.group(1) == "README.md":
                file_link = "https://github.com" + name_match.group(2)
                
                # Fetch the content of README.md
                async with async_playwright() as p:
                    browser = await p.chromium.launch()
                    page = await browser.new_page()
                    await page.goto(file_link)
                    
                    # Wait for the content to load
                    await page.wait_for_selector('article')
                    
                    # Extract the table content from README.md
                    readme_content = await page.evaluate('''() => {
                        const article = document.querySelector('article');
                        return article.innerHTML;
                    }''')
                    
                    await browser.close()
                
                # Parse the README content for job listings
                job_rows = re.findall(r'<tr>.*?</tr>', readme_content, re.DOTALL)
                for job_row in job_rows[1:]:  # Skip the header row
                    cells = re.findall(r'<td.*?>(.*?)</td>', job_row, re.DOTALL)
                    if len(cells) == 5:
                        company, role, location, application_link, date_posted = cells
                        company = re.sub(r'<.*?>', '', company)
                        role = re.sub(r'<.*?>', '', role)
                        location = re.sub(r'<.*?>', '', location)
                        application_link_match = re.search(r'href="([^"]+)"', application_link)
                        application_link = application_link_match.group(1) if application_link_match else ''
                        date_posted = re.sub(r'<.*?>', '', date_posted)
                        
                        jobs.append({
                            'company': company.strip(),
                            'role': role.strip(),
                            'location': location.strip(),
                            'application_link': application_link.strip(),
                            'date_posted': date_posted.strip()
                        })
        
        print(f"Scraped {len(jobs)} jobs.")
        return jobs

def create_database():
    conn = sqlite3.connect('jobs.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS jobs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  unique_id TEXT UNIQUE,
                  company TEXT,
                  role TEXT,
                  location TEXT,
                  application_link TEXT,
                  date_posted TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_applications
                 (user_id INTEGER,
                  job_id INTEGER,
                  FOREIGN KEY(job_id) REFERENCES jobs(id))''')
    conn.commit()
    conn.close()

import hashlib

def create_unique_id(job):
    # Combine relevant fields, including the application link
    identifier_string = (
        f"{job['company'].lower().replace(' ', '_')}_"
        f"{job['role'].lower().replace(' ', '_')}_"
        f"{job['location'].lower().replace(' ', '_')}_"
        f"{job['date_posted']}_"
        f"{job['application_link']}"
    )
    
    # Create a hash of the entire identifier string
    hash_object = hashlib.md5(identifier_string.encode())
    short_hash = hash_object.hexdigest()[:16]  # Use first 8 characters of the hash
    
    # Return only the short hash
    return short_hash

def update_database(jobs):
    conn = sqlite3.connect('jobs.db')
    c = conn.cursor()
    
    new_jobs_count = 0
    updated_jobs_count = 0
    for job in jobs:
        unique_id = create_unique_id(job)
        date_posted = parse_date_posted(job['date_posted'])
        
        # Check if the job already exists
        c.execute("SELECT id FROM jobs WHERE unique_id = ?", (unique_id,))
        existing_job = c.fetchone()
        
        if existing_job:
            # Update existing job
            c.execute('''UPDATE jobs
                         SET company = ?, role = ?, location = ?, application_link = ?, date_posted = ?
                         WHERE unique_id = ?''',
                      (job['company'], job['role'], job['location'],
                       job['application_link'], date_posted, unique_id))
            updated_jobs_count += 1
        else:
            # Insert new job
            c.execute('''INSERT INTO jobs
                         (unique_id, company, role, location, application_link, date_posted)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (unique_id, job['company'], job['role'], job['location'],
                       job['application_link'], date_posted))
            new_jobs_count += 1
    
    conn.commit()
    conn.close()
    
    print(f"Total new jobs added: {new_jobs_count}")
    print(f"Total jobs updated: {updated_jobs_count}")

async def main():
    create_database()
    jobs = await scrape_github_jobs()
    update_database(jobs)
    print(f"Updated database with {len(jobs)} jobs.")

if __name__ == "__main__":
    asyncio.run(main())