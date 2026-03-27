import discord
from discord import app_commands
from discord.ext import commands
import os
import sqlite3

# LOAD TOKEN
token = os.getenv('DISCORD_TOKEN')

# Database Setup
con = sqlite3.connect("meallog.db")
cur = con.cursor()

# Add this to your database setup section
cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_goal(
        user_id INTEGER PRIMARY KEY, 
        calorie_goal INTEGER
    )
""")
con.commit()

cur.execute("""
    CREATE TABLE IF NOT EXISTS meals(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        meal_name TEXT,
        calories INTEGER,
        date DATE DEFAULT CURRENT_DATE
    )
""")
con.commit()


MY_GUILD = discord.Object(id=1144802283188654101)

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True 
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Syncing globally (can take up to an hour to appear everywhere)
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)
        print(f"Synced slash commands for {self.user}")

bot = MyBot()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')

# --- SLASH COMMANDS ---

@bot.tree.command(name="set_goal", description="Set your daily calorie intake goal")
@app_commands.describe(calories="How many calories do you want to eat per day?")
async def set_goal(interaction: discord.Interaction, calories: int):
    user_id = interaction.user.id
    
    try:
        # Use an 'UPSERT' (Insert or Update if the user already exists)
        cur.execute("""
            INSERT INTO daily_goal (user_id, calorie_goal) 
            VALUES (?, ?) 
            ON CONFLICT(user_id) DO UPDATE SET calorie_goal = EXCLUDED.calorie_goal
        """, (user_id, calories))
        con.commit()
        
        await interaction.response.send_message(
            f"🎯 Goal updated! Your daily target is now **{calories}** calories.", 
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

@bot.tree.command(name="ping", description="Check the bot's latency!")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! {round(bot.latency * 1000)}ms")

@bot.tree.command(name="add_meal", description="Log a meal and its calories")
@app_commands.describe(name="What did you eat?", calories="How many calories was it?")
async def add_meal(interaction: discord.Interaction, name: str, calories: int):
    user_id = interaction.user.id
    
    try:
        # Insert the meal into the database
        cur.execute(
            "INSERT INTO meals (user_id, meal_name, calories) VALUES (?, ?, ?)",
            (user_id, name, calories)
        )
        con.commit()
        
        # Now, let's calculate the progress
        # We sum all calories logged by this user TODAY
        cur.execute(
            "SELECT SUM(calories) FROM meals WHERE user_id = ? AND date = CURRENT_DATE",
            (user_id,)
        )
        total_today = cur.fetchone()[0] or 0
        
        # Get their goal to show remaining calories
        cur.execute("SELECT calorie_goal FROM daily_goal WHERE user_id = ?", (user_id,))
        goal_row = cur.fetchone()
        
        if goal_row:
            goal = goal_row[0]
            remaining = goal - total_today
            status_msg = f"Logged **{name}** ({calories} kcal).\n"
            status_msg += f"Total today: **{total_today}/{goal}** kcal. (**{remaining}** left!)"
        else:
            status_msg = f"Logged **{name}** ({calories} kcal). Use `/set_goal` to track progress!"

        await interaction.response.send_message(status_msg, ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)

bot.run(token)
