import discord
from discord.ext import commands
import os  # <- přidané pro načítání tokenu

intents = discord.Intents.default()
intents.reactions = True
intents.messages = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

caps = {}
admin_channel = None

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Bot je online jako: {bot.user} | Slash příkazy: {len(synced)}")
    except Exception as e:
        print(f"Chyba při synchronizaci: {e}")


# ------------------------
# CAP COMMANDS (jen pro adminy)
# ------------------------

@bot.tree.command(name="cap_create", description="Vytvoří novou frontu")
@commands.has_permissions(administrator=True)
async def cap_create(interaction: discord.Interaction, pocet: int, text: str):
    cap_id = len(caps) + 1
    caps[cap_id] = {
        "slots": pocet,
        "text": text,
        "players": [],
        "vip_slots": {},
        "message_id": None,
        "channel_id": None
    }
    await interaction.response.send_message(
        f"✅ Fronta vytvořena (ID: {cap_id}) – {text} ({pocet} slotů)", ephemeral=True
    )


@bot.tree.command(name="cap_remove", description="Odstraní frontu podle ID")
@commands.has_permissions(administrator=True)
async def cap_remove(interaction: discord.Interaction, id: int):
    if id in caps:
        del caps[id]
        await interaction.response.send_message(f"🗑 Fronta {id} byla odstraněna.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Fronta s ID {id} neexistuje.", ephemeral=True)


@bot.tree.command(name="cap_announce", description="Pošle frontu do kanálu")
@commands.has_permissions(administrator=True)
async def cap_announce(interaction: discord.Interaction, kanal: discord.TextChannel, id: int):
    if id not in caps:
        await interaction.response.send_message("❌ Neplatné ID fronty.", ephemeral=True)
        return
    
    cap = caps[id]
    msg = await kanal.send(
        f"🎉 **{cap['text']}**\nSlots: {cap['slots']}\nKlikni na ✅ pro připojení!"
    )
    caps[id]["message_id"] = msg.id
    caps[id]["channel_id"] = kanal.id
    await msg.add_reaction("✅")

    await interaction.response.send_message(
        f"📢 Fronta {id} byla zveřejněna v {kanal.mention}.", ephemeral=True
    )


@bot.tree.command(name="cap_addvip", description="Přidá VIP sloty pro roli")
@commands.has_permissions(administrator=True)
async def cap_addvip(interaction: discord.Interaction, pocet: int, role: discord.Role, id: int):
    if id not in caps:
        await interaction.response.send_message("❌ Neplatné ID fronty.", ephemeral=True)
        return
    
    caps[id]["vip_slots"][role.id] = pocet
    await interaction.response.send_message(
        f"⭐ Pro frontu {id} přidáno {pocet} VIP míst pro roli {role.name}.", ephemeral=True
    )


@bot.tree.command(name="cap_adminchannel", description="Nastaví kanál pro logy")
@commands.has_permissions(administrator=True)
async def cap_adminchannel(interaction: discord.Interaction, kanal: discord.TextChannel):
    global admin_channel
    admin_channel = kanal.id
    await interaction.response.send_message(
        f"⚙️ Admin logy budou posílány do {kanal.mention}.", ephemeral=True
    )


@bot.tree.command(name="cap_list", description="Ukáže seznam hráčů ve frontě")
@commands.has_permissions(administrator=True)
async def cap_list(interaction: discord.Interaction, id: int):
    if id not in caps:
        await interaction.response.send_message("❌ Neplatné ID fronty.", ephemeral=True)
        return
    
    cap = caps[id]
    if not cap["players"]:
        await interaction.response.send_message(f"📋 Fronta {id} je prázdná.", ephemeral=True)
        return

    guild = interaction.guild
    players_mentions = []
    for uid in cap["players"]:
        member = guild.get_member(uid)
        if member:
            players_mentions.append(member.mention)
    
    await interaction.response.send_message(
        f"📋 Fronta {id} – {cap['text']}:\n" + "\n".join(players_mentions),
        ephemeral=True
    )


# ------------------------
# Reakce na připojení do fronty
# ------------------------
@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == bot.user.id:
        return  # ignoruj reakce bota

    for cap_id, cap in caps.items():
        if cap["message_id"] == payload.message_id and str(payload.emoji) == "✅":
            guild = bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)

            # zkontroluj VIP sloty
            is_vip = False
            for role_id, slots in cap["vip_slots"].items():
                if discord.utils.get(member.roles, id=role_id):
                    is_vip = True
                    break

            # kolik VIP už tam je
            vip_count = 0
            for uid in cap["players"]:
                m = guild.get_member(uid)
                if m and any(r.id in cap["vip_slots"] for r in m.roles):
                    vip_count += 1

            # přidání do fronty
            if member.id in cap["players"]:
                await member.send("⚠️ Už jsi přihlášen do této fronty.")
                return

            if is_vip and vip_count < sum(cap["vip_slots"].values()):
                cap["players"].append(member.id)
                await member.send(f"⭐ Jsi přidán do fronty **{cap['text']}** jako VIP!")
            elif len(cap["players"]) < cap["slots"]:
                cap["players"].append(member.id)
                await member.send(f"✅ Byl jsi přidán do fronty **{cap['text']}**.")
            else:
                await member.send("❌ Fronta je plná, nemohl jsi se připojit.")

            # logování do admin kanálu
            if admin_channel:
                channel = guild.get_channel(admin_channel)
                if channel:
                    await channel.send(
                        f"👤 {member.mention} se pokusil připojit do fronty {cap_id} ({cap['text']})."
                    )


# ------------------------
# Spuštění bota přes environment variable
# ------------------------
token = os.environ['DISCORD_TOKEN']
bot.run(token)


