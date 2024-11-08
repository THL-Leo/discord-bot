import asyncio
from playwright.async_api import async_playwright
import re
import sqlite3
from datetime import datetime, timedelta

def parse_date_posted(date_str):
    months = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    
    month, day = date_str.split()
    month_num = months[month[:3]]
    day = int(day)
    current_year = datetime.now().year
    
    # Determine the year
    now = datetime.now() + timedelta(days=1)  # Add 1 day to account for time zone differences
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

def update_database(jobs):
    conn = sqlite3.connect('jobs.db')
    c = conn.cursor()
    
    new_jobs_count = 0
    updated_jobs_count = 0

    # Reverse the jobs list so that the oldest job gets ID 1
    jobs.reverse()

    for i in range(len(jobs)):
        job = jobs[i]  # i-1 because list indices start at 0
        
        # Check if the job with this ID already exists
        c.execute("SELECT * FROM jobs WHERE id = ?", (i,))
        existing_job = c.fetchone()

        date_posted = parse_date_posted(job['date_posted'])

        if existing_job:
            if existing_job[1:] == (job['company'], job['role'], job['location'], job['application_link'], date_posted):
                # No changes, skip this job
                continue
            # Update existing job
            c.execute('''UPDATE jobs
                         SET company = ?, role = ?, location = ?, application_link = ?, date_posted = ?
                         WHERE id = ?''',
                      (job['company'], job['role'], job['location'],
                       job['application_link'], date_posted, i))
            updated_jobs_count += 1
            print(f"Job updated: ID {i} - {job['company']} - {job['role']}")
        else:
            # Insert new job
            c.execute('''INSERT INTO jobs
                         (id, company, role, location, application_link, date_posted)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (i, job['company'], job['role'], job['location'],
                       job['application_link'], date_posted))
            new_jobs_count += 1
            print(f"New job added: ID {i} - {job['company']} - {job['role']}")

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