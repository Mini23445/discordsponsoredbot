import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import re
from typing import Optional

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# File to store user stats
STATS_FILE = "gem_stats.json"

# Configuration - UPDATE THESE VALUES
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))  # Admin role ID from env variable
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))  # Log channel ID from env variable

# Load stats from JSON file
def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, 'r') as f:
            return json.load(f)
    return {}

# Save stats to JSON file
def save_stats(stats):
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=4)

# Check if user has admin role
def is_admin(interaction: discord.Interaction):
    return any(role.id == ADMIN_ROLE_ID for role in interaction.user.roles)

# Get user's stats
def get_user_stats(user_id):
    stats = load_stats()
    user_id_str = str(user_id)
    if user_id_str not in stats:
        stats[user_id_str] = {"gems_given": 0}
    return stats[user_id_str]

# Update user's stats
def update_user_stats(user_id, amount):
    stats = load_stats()
    user_id_str = str(user_id)
    if user_id_str not in stats:
        stats[user_id_str] = {"gems_given": 0}
    stats[user_id_str]["gems_given"] += amount
    save_stats(stats)
    return stats[user_id_str]["gems_given"]

# Format large numbers with commas
def format_number(number):
    return f"{number:,}"

# Parse amount input (supports numbers, k, m, b suffixes)
def parse_amount(amount_str):
    # If it's already a number, return it
    if isinstance(amount_str, int):
        return amount_str
    
    # Remove any commas
    amount_str = str(amount_str).replace(',', '')
    
    # Check for suffix
    if amount_str.lower().endswith('k'):
        return int(float(amount_str[:-1]) * 1000)
    elif amount_str.lower().endswith('m'):
        return int(float(amount_str[:-1]) * 1000000)
    elif amount_str.lower().endswith('b'):
        return int(float(amount_str[:-1]) * 1000000000)
    else:
        return int(amount_str)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# Stats command - shows user's own stats
@bot.tree.command(name="stats", description="Check how many gems you've given away")
async def stats(interaction: discord.Interaction):
    user_stats = get_user_stats(interaction.user.id)
    gems = user_stats["gems_given"]
    formatted_gems = format_number(gems)
    
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.set_footer(text="Keep up the good work!")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Log command - admin only
@bot.tree.command(name="log", description="Log gems given to a user (Admin only)")
@app_commands.describe(user="The user to log gems for", amount="The amount of gems to log (supports k, m, b suffixes)")
async def log(interaction: discord.Interaction, user: discord.User, amount: str):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ You need admin permissions to use this command.", ephemeral=True)
        return
    
    try:
        parsed_amount = parse_amount(amount)
    except ValueError:
        await interaction.response.send_message("❌ Invalid amount format. Use numbers or suffixes like k, m, b (e.g., 10k, 5m, 1b).", ephemeral=True)
        return
    
    if parsed_amount <= 0:
        await interaction.response.send_message("❌ Amount must be a positive number.", ephemeral=True)
        return
    
    new_total = update_user_stats(user.id, parsed_amount)
    formatted_amount = format_number(parsed_amount)
    formatted_total = format_number(new_total)
    
    # Send confirmation to admin
    embed = discord.Embed(
        title="✅ Gems Logged Successfully",
        color=0x00ff00
    )
    embed.add_field(name="User", value=user.name, inline=True)
    embed.add_field(name="Amount Added", value=f"{formatted_amount} 💎", inline=True)
    embed.add_field(name="New Total", value=f"{formatted_total} 💎", inline=True)
    embed.set_footer(text=f"Logged by {interaction.user.name}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Send to log channel
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        log_embed = discord.Embed(
            title="💎 Gem Donation Logged",
            color=0x0099ff
        )
        log_embed.add_field(name="Donor", value=user.name, inline=True)
        log_embed.add_field(name="Amount", value=f"{formatted_amount} 💎", inline=True)
        log_embed.add_field(name="Total Donated", value=f"{formatted_total} 💎", inline=True)
        log_embed.add_field(name="Admin", value=interaction.user.name, inline=True)
        log_embed.set_thumbnail(url=user.display_avatar.url)
        log_embed.set_footer(text="Gem Tracking System")
        
        await log_channel.send(embed=log_embed)

# Remove stats command - admin only
@bot.tree.command(name="removestats", description="Remove gems from a user's stats (Admin only)")
@app_commands.describe(user="The user to remove gems from", amount="The amount of gems to remove (supports k, m, b suffixes)")
async def removestats(interaction: discord.Interaction, user: discord.User, amount: str):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ You need admin permissions to use this command.", ephemeral=True)
        return
    
    try:
        parsed_amount = parse_amount(amount)
    except ValueError:
        await interaction.response.send_message("❌ Invalid amount format. Use numbers or suffixes like k, m, b (e.g., 5m, 1b).", ephemeral=True)
        return
    
    if parsed_amount <= 0:
        await interaction.response.send_message("❌ Amount must be a positive number.", ephemeral=True)
        return
    
    user_stats = get_user_stats(user.id)
    if parsed_amount > user_stats["gems_given"]:
        await interaction.response.send_message("❌ Cannot remove more gems than the user has.", ephemeral=True)
        return
    
    new_total = update_user_stats(user.id, -parsed_amount)
    formatted_amount = format_number(parsed_amount)
    formatted_total = format_number(new_total)
    
    embed = discord.Embed(
        title="✅ Gems Removed Successfully",
        color=0xff9900
    )
    embed.add_field(name="User", value=user.name, inline=True)
    embed.add_field(name="Amount Removed", value=f"{formatted_amount} 💎", inline=True)
    embed.add_field(name="New Total", value=f"{formatted_total} 💎", inline=True)
    embed.set_footer(text=f"Updated by {interaction.user.name}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Send to log channel
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        log_embed = discord.Embed(
            title="💎 Gems Removed",
            color=0xff0000
        )
        log_embed.add_field(name="User", value=user.name, inline=True)
        log_embed.add_field(name="Amount Removed", value=f"{formatted_amount} 💎", inline=True)
        log_embed.add_field(name="Total Donated", value=f"{formatted_total} 💎", inline=True)
        log_embed.add_field(name="Admin", value=interaction.user.name, inline=True)
        log_embed.set_thumbnail(url=user.display_avatar.url)
        log_embed.set_footer(text="Gem Tracking System")
        
        await log_channel.send(embed=log_embed)

# Adminstats command - view other users' stats
@bot.tree.command(name="adminstats", description="View another user's gem stats (Admin only)")
@app_commands.describe(user="The user whose stats you want to view")
async def adminstats(interaction: discord.Interaction, user: discord.User):
    if not is_admin(interaction):
        await interaction.response.send_message("❌ You need admin permissions to use this command.", ephemeral=True)
        return
    
    user_stats = get_user_stats(user.id)
    gems = user_stats["gems_given"]
    formatted_gems = format_number(gems)
    
    embed = discord.Embed(
        title="💎 Admin Gem Stats",
        description=f"**{user.name}**'s donation history",
        color=0x0099ff
    )
    embed.add_field(
        name="Total Gems Given",
        value=f"```{formatted_gems} 💎```",
        inline=False
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=f"Requested by {interaction.user.name}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Run the bot
if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
