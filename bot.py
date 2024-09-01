import os
import discord
from discord.ext import tasks
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from datetime import datetime
import asyncio
import json

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

async def scrape_apple_refurbished():
    products = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto('https://www.apple.com/shop/refurbished/mac')

        product_tiles = page.locator('.rf-refurb-producttile')

        product_count = await product_tiles.count()

        for i in range(product_count):
            tile = product_tiles.nth(i)
            await tile.scroll_into_view_if_needed(timeout=5000)
            title = tile.locator('.rf-refurb-producttile-title a')
            price = tile.locator('span.rf-refurb-producttile-currentprice')
            previous_price = tile.locator('span.rf-refurb-price-previousprice')
            savings = tile.locator('span.rf-refurb-price-savingsprice')
            link = await title.get_attribute('href')
            picture = tile.locator('.rf-refurb-producttile-image')

            if title and price:
                product_info = {
                    'title': await title.inner_text(),
                    'price': await price.inner_text(),
                    'previous_price': await previous_price.inner_text() if await previous_price.count() > 0 else 'N/A',
                    'savings': await savings.inner_text() if await savings.count() > 0 else 'N/A',
                    'link': 'https://www.apple.com' + link,
                    'picture': await picture.get_attribute('src')
                }
                products.append(product_info)

        await browser.close()
    return products


async def embedding(product):
    product_title = product['title']
    product_price = product['price']
    product_previous_price = product['previous_price'].replace('Was\n', '')
    product_savings = product['savings'].replace('Save ', '')
    product_link = product['link']
    product_img = product['picture']
    embed = discord.Embed(title=f"{product_title}",
                      url=f"{product_link}",
                      colour=0x00b0f4,
                      timestamp=datetime.now())
    embed.add_field(name="Refurbished Price",
                value=f"{product_price}",
                inline=True)
    embed.add_field(name="Original Price",
                    value=f"{product_previous_price}",
                    inline=True)
    embed.add_field(name="You Saved",
                value=f"{product_savings}",
                inline=True)

    embed.set_image(url=f"{product_img}")

    return embed

@tasks.loop(hours=1)
async def scrape_task():
    channel = client.get_channel(int(os.getenv('CHANNEL_ID')))
    scraped_data = await scrape_apple_refurbished()
    for product in scraped_data:
        embed = await embedding(product)
        await channel.send(embed=embed)
    # embed = await embedding(scraped_data[0])
    # await channel.send(embed=embed)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    scrape_task.start()

@client.event
async def on_message(message):
    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')

client.run(os.getenv('BOT_TOKEN'))
