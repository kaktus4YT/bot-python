import discord
from discord.ext import commands, tasks
from discord.utils import get
import asyncio
import os
from discord import app_commands
import logging
import random
import datetime
from discord.ui import Button, View
import json
from datetime import datetime, timedelta
from mcrcon import MCRcon


intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

DATA_FILE = "data.json"

GUILD_ID = ""
RCON_HOST = "localhost"  # Adres serwera Minecraft
RCON_PORT = 25575        # Domyślny port RCON
RCON_PASSWORD = ""  # Hasło RCON

giveaways = {}
support_data = {}

LEVELS_FILE = "levels.json"

@bot.event
async def on_ready():
    await tree.sync()  # Synchronizuje slash komendy z Discordem
    print(f'Zalogowano jako {bot.user}')
    print(f'Bot zalogowany jako {bot.user}')
    guild = discord.utils.get(bot.guilds, id=int(GUILD_ID))
    print("Komendy zarejestrowane")

    guild = discord.Object(id=GUILD_ID)

    try:
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print("Komendy zostały zsynchronizowane.")
    except Exception as e:
        print(f"Błąd synchronizacji komend: {e}")

# Klasa do obsługi przycisków
class TicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Otwórz Ticket", style=discord.ButtonStyle.green)
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("Wystąpił problem. Nie można odnaleźć serwera.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        
        existing_channel = get(guild.channels, name=f'ticket-{interaction.user.name.lower()}')
        if existing_channel:
            await interaction.followup.send(f'Masz już otwarty ticket: {existing_channel.mention}', ephemeral=True)
            return

        category = get(guild.categories, name="Tickety")
        
        if not category:
            category = await guild.create_category("Tickety")
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        
        channel = await category.create_text_channel(f'ticket-{interaction.user.name}', overwrites=overwrites)
        await channel.send(
            f'{interaction.user.mention}, Twoje zgłoszenie zostało utworzone. Opisz swój problem, a ktoś z administracji Ci pomoże!',
            view=CloseTicketButton()
        )
        logger.info(f'Użytkownik {interaction.user} otworzył ticket: {channel.name}')  # Logowanie tworzenia ticketu
        await interaction.followup.send(f'Twój ticket został utworzony: {channel.mention}', ephemeral=True)

class CloseTicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Zamknij Ticket", style=discord.ButtonStyle.red)
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        if "ticket-" in channel.name:
            await interaction.response.send_message(f'Ticket zostanie zamknięty za 5 sekund...', ephemeral=True)
            await asyncio.sleep(5)

            transcript = f"Transkrypt kanału: {channel.name}\n\n"
            async for message in channel.history(limit=None):
                transcript += f"{message.created_at.strftime('%Y-%m-%d %H:%M:%S')} - {message.author.display_name}: {message.content}\n"
            transcript_filename = f"transcript_{channel.name}.txt"
            with open(transcript_filename, "w", encoding="utf-8") as file:
                file.write(transcript)

            admin_channel_id = 1278970391225958451  # Zastąp to rzeczywistym ID kanału
            admin_channel = interaction.guild.get_channel(admin_channel_id)
            if admin_channel:
                await admin_channel.send(file=discord.File(transcript_filename))

            await interaction.user.send("Twój ticket został zamknięty. Oto transkrypt rozmowy:", file=discord.File(transcript_filename))
            os.remove(transcript_filename)
            
            logger.info(f'Ticket {channel.name} został zamknięty przez {interaction.user}')  # Logowanie zamknięcia ticketu
            await channel.delete()
        else:
            await interaction.response.send_message("Nie możesz zamknąć tego kanału, ponieważ nie jest to ticket.", ephemeral=True)

# Komenda do wyświetlania panelu z przyciskiem do otwierania ticketu na kanale, na którym komenda została użyta
@tree.command(name="panel", description="Wyświetla panel do tworzenia ticketów na bieżącym kanale")
async def panel(interaction: discord.Interaction):
    channel = interaction.channel  # Pobiera kanał, na którym została użyta komenda

    embed = discord.Embed(
        title="Pomoc",
        description="Kliknij przycisk poniżej, aby otworzyć ticket.",
        color=discord.Color.green()
    )
    view = TicketButton()
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message(f'Panel do tworzenia ticketów został wysłany na {channel.mention}.', ephemeral=True)

@tree.command(name="close", description="Zamyka ticket i tworzy transkrypt")
async def close(interaction: discord.Interaction):
    channel = interaction.channel
    if "ticket-" in channel.name:
        transcript = f"Transkrypt kanału: {channel.name}\n\n"
        
        async for message in channel.history(limit=None):
            transcript += f"{message.created_at.strftime('%Y-%m-%d %H:%M:%S')} - {message.author.display_name}: {message.content}\n"
        
        transcript_filename = f"transcript_{channel.name}.txt"
        with open(transcript_filename, "w", encoding="utf-8") as file:
            file.write(transcript)
        
        admin_channel_id = 1278970391225958451  # Zastąp to rzeczywistym ID kanału
        admin_channel = interaction.guild.get_channel(admin_channel_id)
        if admin_channel:
            await admin_channel.send(file=discord.File(transcript_filename))

        await interaction.user.send("Twój ticket został zamknięty. Oto transkrypt rozmowy:", file=discord.File(transcript_filename))
        os.remove(transcript_filename)
        
        await interaction.response.send_message(f'Ten ticket zostanie zamknięty za 5 sekund...', ephemeral=True)
        await asyncio.sleep(5)
        await channel.delete()
    else:
        await interaction.response.send_message("Nie możesz zamknąć tego kanału, ponieważ nie jest to ticket.", ephemeral=True)

@tree.command(name="adduser", description="Dodaje użytkownika do ticketu")
@app_commands.describe(member="Członek do dodania")
async def adduser(interaction: discord.Interaction, member: discord.Member):
    channel = interaction.channel
    if "ticket-" in channel.name:
        await channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
        await interaction.response.send_message(f'{member.mention} został dodany do ticketu.', ephemeral=True)
    else:
        await interaction.response.send_message("Ta komenda może być używana tylko w kanałach ticketu.", ephemeral=True)

@tree.command(name="removeuser", description="Usuwa użytkownika z ticketu")
@app_commands.describe(member="Członek do usunięcia")
async def removeuser(interaction: discord.Interaction, member: discord.Member):
    channel = interaction.channel
    if "ticket-" in channel.name:
        await channel.set_permissions(member, overwrite=None)
        await interaction.response.send_message(f'{member.mention} został usunięty z ticketu.', ephemeral=True)
    else:
        await interaction.response.send_message("Ta komenda może być używana tylko w kanałach ticketu.", ephemeral=True)

@tree.command(name="rename", description="Zmienia nazwę kanału ticketu")
@app_commands.describe(new_name="Nowa nazwa kanału")
async def rename(interaction: discord.Interaction, new_name: str):
    channel = interaction.channel
    if "ticket-" in channel.name:
        old_name = channel.name
        await channel.edit(name=new_name)
        await interaction.response.send_message(f'Nazwa kanału została zmieniona z `{old_name}` na `{new_name}`.', ephemeral=True)
    else:
        await interaction.response.send_message("Ta komenda może być używana tylko w kanałach ticketu.", ephemeral=True)

# Function to end a giveaway based on prize name
async def end_giveaway(prize):
    giveaway = giveaways.get(prize)
    if giveaway and giveaway["active"]:
        channel = giveaway["channel"]
        message = await channel.fetch_message(giveaway["message_id"])
        users = []
        
        async for user in message.reactions[0].users():
            if user != bot.user:
                users.append(user)
        
        if len(users) == 0:
            await channel.send(f'Nikt nie wziął udziału w giveaway na **{prize}**.')
        else:
            winner = random.choice(users)
            await channel.send(f'🎉 Gratulacje, {winner.mention}! Wygrałeś **{prize}**!')
            await winner.send(f'Gratulacje! Wygrałeś **{prize}** w giveaway na serwerze {channel.guild.name}!')
            logger.info(f'Giveaway zakończony. Nagroda: {prize}, Zwycięzca: {winner}')
            
            # Debug print to check role assignment
            print(f"Looking for role: {prize}")
            
            # Assign the role if the prize is a role
            role = discord.utils.get(channel.guild.roles, name=prize)
            if role:
                print(f"Role found: {role.name}")
                await winner.add_roles(role)
                await channel.send(f'{winner.mention} otrzymał rolę **{prize}** jako nagrodę!')
                await winner.send(f'Otrzymałeś rolę **{prize}** na serwerze {channel.guild.name} jako nagrodę!')
            else:
                print(f"Role not found: {prize}")

        giveaways[prize]["active"] = False
    else:
        logger.warning(f"Próba zakończenia giveaway, który nie istnieje lub został już zakończony.")

# Command to start a giveaway
@tree.command(name="giveaway", description="Rozpoczyna giveaway")
@app_commands.describe(prize="Nagroda w giveaway", duration="Czas trwania (np. 10m, 1h)")
async def giveaway(interaction: discord.Interaction, prize: str, duration: str):
    time_multiplier = {"m": 60, "h": 3600, "d": 86400}
    unit = duration[-1]

    if unit not in time_multiplier:
        await interaction.response.send_message("Podaj poprawny czas trwania, np. 10m, 1h, 1d.", ephemeral=True)
        return

    try:
        duration_seconds = int(duration[:-1]) * time_multiplier[unit]
    except ValueError:
        await interaction.response.send_message("Podaj poprawny czas trwania, np. 10m, 1h, 1d.", ephemeral=True)
        return

    end_time = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=duration_seconds)
    giveaway_embed = discord.Embed(
        title="🎉 Giveaway! 🎉",
        description=f"Wygraj **{prize}**!\nReaguj 🎉, aby wziąć udział!",
        color=discord.Color.blue(),
        timestamp=end_time
    )
    giveaway_embed.set_footer(text="Zakończenie")

    message = await interaction.channel.send(embed=giveaway_embed)
    await message.add_reaction("🎉")
    await interaction.response.send_message(f'Giveaway o nagrodę **{prize}** został rozpoczęty!', ephemeral=True)

    # Store giveaway data, using prize as the key
    giveaways[prize] = {
        "channel": interaction.channel,
        "prize": prize,
        "end_time": end_time,
        "message_id": message.id,
        "active": True
    }

    await asyncio.sleep(duration_seconds)

    # End the giveaway if it hasn't been ended early
    if giveaways[prize]["active"]:
        await end_giveaway(prize)

# Command to end a giveaway based on prize name
@tree.command(name="end_giveaway", description="Przedwcześnie kończy giveaway")
@app_commands.describe(prize="Nazwa nagrody w giveaway")
async def end_giveaway_command(interaction: discord.Interaction, prize: str):
    if prize in giveaways and giveaways[prize]["active"]:
        await end_giveaway(prize)
        await interaction.response.send_message(f'Giveaway na **{prize}** został zakończony przedwcześnie.', ephemeral=True)
    else:
        await interaction.response.send_message(f'Nie znaleziono aktywnego giveaway z nagrodą **{prize}**.', ephemeral=True)

# Error handling for app commands
@tree.error
async def on_tree_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if interaction.response.is_done():
        await interaction.followup.send("Wystąpił błąd przy wykonywaniu komendy.", ephemeral=True)
    else:
        await interaction.response.send_message("Wystąpił błąd przy wykonywaniu komendy.", ephemeral=True)
    logger.error(f'Wystąpił błąd w komendzie: {error}')


# Komenda do banowania użytkownika
@tree.command(name="ban", description="Banuje użytkownika")
@app_commands.describe(member="Użytkownik do zbanowania", reason="Powód zbanowania")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = None):
    await member.send(f"Zostałeś zbanowany na serwerze {interaction.guild.name} za: {reason}")
    await member.ban(reason=reason)
    await interaction.channel.send(f'{member.mention} został zbanowany za: {reason}.')
    await interaction.response.send_message(f'{member.mention} został zbanowany za: {reason}', ephemeral=True)

# Komenda do odbanowania użytkownika
@tree.command(name="unban", description="Odbanowuje użytkownika")
@app_commands.describe(member="Użytkownik do odbanowania (format: nazwa#1234)")
async def unban(interaction: discord.Interaction, member: str):
    banned_users = await interaction.guild.bans()
    member_name, member_discriminator = member.split('#')

    for ban_entry in banned_users:
        user = ban_entry.user

        if (user.name, user.discriminator) == (member_name, member_discriminator):
            await interaction.guild.unban(user)
            await interaction.channel.send(f'{user.mention} został odbanowany.')
            await user.send(f"Zostałeś odbanowany na serwerze {interaction.guild.name}.")
            await interaction.response.send_message(f'{user.mention} został odbanowany.', ephemeral=True)
            return

    await interaction.response.send_message(f'Użytkownik {member} nie został znaleziony w liście zbanowanych.', ephemeral=True)

# Modal do zbierania opinii lub zgłoszeń od użytkowników z dwoma pytaniami
class FeedbackModal(discord.ui.Modal, title="Zgłoszenie"):
    question1 = discord.ui.TextInput(
        label="Nick Minecraft",
        style=discord.TextStyle.short,
        placeholder="",
        required=True,
        max_length=100
    )

    question2 = discord.ui.TextInput(
        label="Wiek",
        style=discord.TextStyle.short,
        placeholder="",
        required=True,
        max_length=100
    )

    question3 = discord.ui.TextInput(
        label="Doświadczenie",
        style=discord.TextStyle.long,
        placeholder="",
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Wyślij treść modalu na określony kanał
        admin_channel_id = 1269255707296010342  # Zastąp to rzeczywistym ID kanału
        admin_channel = interaction.guild.get_channel(admin_channel_id)
        if admin_channel:
            embed = discord.Embed(
                title="Nowe zgłoszenie",
                color=discord.Color.green()
            )
            embed.add_field(name="Nick Minecraft", value=self.question1.value, inline=False)
            embed.add_field(name="Wiek", value=self.question2.value or "Brak odpowiedzi", inline=False)
            embed.add_field(name="Doświadczenie", value=self.question3.value or "Brak odpowiedzi", inline=False)
            embed.add_field(name="Użytkownik", value=interaction.user.mention, inline=False)
            await admin_channel.send(embed=embed)
            await interaction.response.send_message("Dziękujemy za Twoje zgłoszenie!", ephemeral=True)
        else:
            await interaction.response.send_message("Wystąpił problem przy wysyłaniu opinii.", ephemeral=True)

@tree.command(name="zgłoszenie", description="Otwiera formularz do przesłania zgłoszenia")
async def feedback(interaction: discord.Interaction):
    # Wyświetlenie modalu
    modal = FeedbackModal()
    await interaction.response.send_modal(modal)

# Komenda do wysyłania propozycji do administracji
@tree.command(name="propozycja", description="Wysyła propozycję do administracji")
@app_commands.describe(content="Treść propozycji")
async def propozycja(interaction: discord.Interaction, content: str):
    admin_channel_id = 1277889128565968958  # Zastąp to rzeczywistym ID kanału

    admin_channel = bot.get_channel(admin_channel_id)
    if admin_channel:
        embed = discord.Embed(
            title="Nowa propozycja",
            description=content,
            color=discord.Color.green()
        )
        embed.add_field(name="Użytkownik", value=interaction.user.mention, inline=False)
        embed.set_footer(text=f"ID propozycji: {interaction.id}")

        await admin_channel.send(embed=embed)
        await interaction.response.send_message(f'Twoja propozycja została wysłana do administracji!', ephemeral=True)
    else:
        await interaction.response.send_message('Nie udało się znaleźć kanału administracyjnego. Sprawdź konfigurację.', ephemeral=True)

@tree.command(name="propozycja_akceptuj", description="Akceptuje propozycję użytkownika")
@app_commands.describe(proposal_id="ID wiadomości z propozycją")
async def propozycja_akceptuj(interaction: discord.Interaction, proposal_id: int):
    try:
        # Próba pobrania wiadomości na podstawie ID
        proposal_message = await interaction.channel.fetch_message(proposal_id)
    except discord.NotFound:
        # Wiadomość nie została znaleziona
        await interaction.response.send_message(f'Nie znaleziono wiadomości o ID {proposal_id}.', ephemeral=True)
        return
    except discord.Forbidden:
        # Brak dostępu do kanału/wiadomości
        await interaction.response.send_message('Nie mam uprawnień do pobrania tej wiadomości.', ephemeral=True)
        return
    except discord.HTTPException:
        # Ogólny błąd HTTP
        await interaction.response.send_message('Wystąpił błąd przy pobieraniu wiadomości.', ephemeral=True)
        return

    # Jeśli wiadomość została pomyślnie pobrana, kontynuujemy proces
    user_mention = proposal_message.embeds[0].fields[0].value
    user = await commands.MemberConverter().convert(interaction, user_mention)
    
    if user:
        await user.send(f'Twoja propozycja (ID: {proposal_id}) została zaakceptowana!')
        await interaction.response.send_message(f'Propozycja {proposal_id} została zaakceptowana.', ephemeral=True)
    else:
        await interaction.response.send_message('Nie udało się wysłać wiadomości prywatnej do użytkownika.', ephemeral=True)


@tree.command(name="propozycja_odrzuc", description="Odrzuca propozycję użytkownika")
@app_commands.describe(proposal_id="ID wiadomości z propozycją")
async def propozycja_odrzuc(interaction: discord.Interaction, proposal_id: int):
    proposal_message = await interaction.channel.fetch_message(proposal_id)
    if proposal_message:
        user_mention = proposal_message.embeds[0].fields[0].value
        user = await commands.MemberConverter().convert(interaction, user_mention)
        if user:
            await user.send(f'Twoja propozycja (ID: {proposal_id}) została odrzucona.')
            await interaction.response.send_message(f'Propozycja {proposal_id} została odrzucona.', ephemeral=True)
        else:
            await interaction.response.send_message('Nie udało się wysłać wiadomości prywatnej do użytkownika.', ephemeral=True)
    else:
        await interaction.response.send_message('Nie znaleziono wiadomości z tą propozycją.', ephemeral=True)

# Konfiguracja systemu logów
logging.basicConfig(
    level=logging.INFO,  # Możesz ustawić poziom logowania na DEBUG, INFO, WARNING, ERROR, CRITICAL
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('discord_bot.log'),  # Logi będą zapisywane do pliku 'discord_bot.log'
        logging.StreamHandler()  # Logi będą również wyświetlane w konsoli
    ]
)

logger = logging.getLogger(__name__)

@bot.event
async def on_command_error(ctx, error):
    logger.error(f'Wystąpił błąd: {str(error)}')
    await ctx.send(f'Wystąpił błąd: {str(error)}')

@bot.command()
@commands.has_permissions(manage_roles=True)
async def awans(ctx, member: discord.Member, role: discord.Role):
    try:
        await member.add_roles(role)
        await ctx.send(f'Awansowano {member.mention} na rolę {role.name}.')
    except discord.Forbidden:
        await ctx.send('Nie mam uprawnień do zarządzania rolami.')
    except discord.HTTPException as e:
        await ctx.send(f'Wystąpił błąd: {e}')

@bot.command()
@commands.has_permissions(administrator=True)
async def degrad(ctx, member: discord.Member, role: discord.Role):
    try:
        await member.remove_roles(role)
        await ctx.send(f'Zdegradowano {member.mention} z roli {role.name}.')
    except discord.Forbidden:
        await ctx.send('Nie mam uprawnień do zarządzania rolami.')
    except discord.HTTPException as e:
        await ctx.send(f'Wystąpił błąd: {e}')

# Kanał do logów
LOG_CHANNEL_ID = 1275890698737942598  # Podaj ID kanału, na którym chcesz wysyłać logi

# Logowanie dołączenia użytkownika
@bot.event
async def on_member_join(member):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    await log_channel.send(f'{member} dołączył do serwera.')

# Logowanie opuszczenia użytkownika
@bot.event
async def on_member_remove(member):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    await log_channel.send(f'{member} opuścił serwer.')

# Logowanie usunięcia wiadomości
@bot.event
async def on_message_delete(message):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    await log_channel.send(f'Wiadomość od {message.author} została usunięta z kanału {message.channel}: {message.content}')

# Logowanie edycji wiadomości
@bot.event
async def on_message_edit(before, after):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    await log_channel.send(f'Wiadomość od {before.author} na kanale {before.channel} została edytowana z "{before.content}" na "{after.content}"')

# Logowanie dodawania roli użytkownikowi
@bot.event
async def on_member_update(before, after):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    
    # Sprawdzenie dodanych ról
    added_roles = [role for role in after.roles if role not in before.roles]
    removed_roles = [role for role in before.roles if role not in after.roles]

    if added_roles:
        await log_channel.send(f'{after} otrzymał rolę: {", ".join(role.name for role in added_roles)}')
    if removed_roles:
        await log_channel.send(f'{after} stracił rolę: {", ".join(role.name for role in removed_roles)}')

@bot.command()
async def weryfikacja(ctx):
    # Tworzenie embeda
    embed = discord.Embed(title="Weryfikacja", description="Kliknij przycisk poniżej, aby zweryfikować i uzyskać rolę.", color=discord.Color.green())

    # Tworzenie przycisku
    button = Button(label="Zweryfikuj się", style=discord.ButtonStyle.success)

    async def button_callback(interaction):
        role = discord.utils.get(interaction.guild.roles, name="📺・Gracz")  # Zmień "Zweryfikowany" na nazwę roli, którą chcesz nadać
        if role:
            if role not in interaction.user.roles:
                await interaction.user.add_roles(role)
                await interaction.response.send_message("Pomyślnie zweryfikowano! Otrzymałeś rolę.", ephemeral=True)
            else:
                await interaction.response.send_message("Już posiadasz tę rolę.", ephemeral=True)
        else:
            await interaction.response.send_message("Rola nie została znaleziona.", ephemeral=True)

    button.callback = button_callback

    # Tworzenie widoku i dodawanie przycisku
    view = View()
    view.add_item(button)

    # Wysyłanie wiadomości z embedem i przyciskiem
    await ctx.send(embed=embed, view=view)

# Funkcja do ładowania danych z pliku JSON
def load_levels():
    if os.path.exists(LEVELS_FILE):
        with open(LEVELS_FILE, "r") as file:
            return json.load(file)
    return {}

# Funkcja do zapisywania danych do pliku JSON
def save_levels(levels):
    with open(LEVELS_FILE, "w") as file:
        json.dump(levels, file, indent=4)

# Funkcja do obliczania potrzebnego XP na dany poziom
def xp_for_next_level(level):
    return 5 * (level ** 2) + 50 * level + 100

# Event, który uruchamia się przy każdej wiadomości
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    levels = load_levels()

    user_id = str(message.author.id)
    if user_id not in levels:
        levels[user_id] = {"xp": 0, "level": 1}

    levels[user_id]["xp"] += 10  # Przyznaj 10 XP za każdą wiadomość

    current_xp = levels[user_id]["xp"]
    current_level = levels[user_id]["level"]
    next_level_xp = xp_for_next_level(current_level)

    if current_xp >= next_level_xp:
        levels[user_id]["level"] += 1
        levels[user_id]["xp"] = current_xp - next_level_xp
        await message.channel.send(f"Gratulacje, {message.author.mention}! Osiągnąłeś poziom {levels[user_id]['level']}!")

    save_levels(levels)

    await bot.process_commands(message)

# Komenda do sprawdzania poziomu użytkownika
@bot.command(name="poziom")
async def level(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    levels = load_levels()
    user_id = str(member.id)

    if user_id in levels:
        await ctx.send(f"{member.mention} jest na poziomie {levels[user_id]['level']} z {levels[user_id]['xp']} XP.")
    else:
        await ctx.send(f"{member.mention} nie zdobył jeszcze żadnego XP.")


# Funkcja do zapisywania danych do pliku
def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        # Tworzymy pustą strukturę, jeśli plik nie istnieje
        save_data({})
        return {}
    except json.JSONDecodeError:
        # Obsługa błędu, jeśli plik jest uszkodzony lub pusty
        print("Błąd: Plik JSON jest uszkodzony. Tworzenie nowego pliku.")
        save_data({})
        return {}        

# Funkcja do rejestrowania mutów i warnów
def log_action(user_id, action, reason=None, duration=None):
    data = load_data()
    if str(user_id) not in data:
        data[str(user_id)] = {"mutes": [], "warns": []}

    if action == "mute":
        mute_info = {
            "timestamp": str(datetime.utcnow()),
            "reason": reason,
            "duration": duration  # Czas trwania w minutach
        }
        data[str(user_id)]["mutes"].append(mute_info)
    elif action == "warn":
        warn_info = {
            "timestamp": str(datetime.utcnow()),
            "reason": reason
        }
        data[str(user_id)]["warns"].append(warn_info)

    save_data(data)

# Funkcja do tworzenia roli muta, jeśli jej nie ma
async def create_mute_role(guild):
    mute_role = discord.utils.get(guild.roles, name="Muted")
    if mute_role is None:
        permissions = discord.Permissions(send_messages=False, speak=False)
        mute_role = await guild.create_role(name="Muted", permissions=permissions)
        
        # Ustawienia kanałów, aby uniemożliwić wysyłanie wiadomości
        for channel in guild.channels:
            await channel.set_permissions(mute_role, send_messages=False, speak=False)
    
    return mute_role

# Funkcja do sprawdzania, czy mute wygasł
def is_mute_expired(mute):
    mute_time = datetime.fromisoformat(mute["timestamp"])
    duration = timedelta(minutes=mute["duration"])
    return datetime.utcnow() > mute_time + duration

# Task automatycznie sprawdzający wygasłe muty
@tasks.loop(minutes=1)
async def check_mutes():
    print("Rozpoczęcie zadania sprawdzania mutów...")
    try:
        data = load_data()
        for guild in bot.guilds:
            print(f"Sprawdzanie serwera: {guild.name}")
            mute_role = await create_mute_role(guild)
            for user_id, user_data in data.items():
                member = guild.get_member(int(user_id))
                if member is None:
                    continue

                # Sprawdzenie aktywnych mutów
                active_mutes = []
                for mute in user_data["mutes"]:
                    if not is_mute_expired(mute):
                        active_mutes.append(mute)
                    else:
                        # Jeśli mute wygasł, zdejmujemy rolę "Muted"
                        if mute_role in member.roles:
                            await member.remove_roles(mute_role)
                            await member.send(f"Twój mute na serwerze {guild.name} wygasł.")
                user_data["mutes"] = active_mutes
        save_data(data)
    except Exception as e:
        print(f"Błąd w zadaniu check_mutes: {e}")

# Komenda do nałożenia muta
@bot.command()
async def mute(ctx, member: discord.Member, duration: int, *, reason=None):
    # Rejestrujemy muta
    log_action(member.id, "mute", reason, duration)
    
    # Tworzymy lub uzyskujemy rolę "Muted"
    mute_role = await create_mute_role(ctx.guild)
    
    # Nadajemy rolę wyciszenia
    await member.add_roles(mute_role)
    
    await ctx.send(f"{member.name} został wyciszony na {duration} minut. Powód: {reason or 'Brak powodu'}")

# Komenda do usunięcia muta (unmute)
@bot.command()
async def unmute(ctx, member: discord.Member):
    data = load_data()
    
    if str(member.id) not in data or not data[str(member.id)]["mutes"]:
        await ctx.send(f"{member.name} nie ma aktywnych mutów.")
        return
    
    # Usuwamy ostatni mute
    last_mute = data[str(member.id)]["mutes"].pop()
    save_data(data)
    
    # Usuwamy rolę "Muted"
    mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if mute_role in member.roles:
        await member.remove_roles(mute_role)
    
    await ctx.send(f"Ostatni mute dla {member.name} z dnia {last_mute['timestamp']} został usunięty.")

# Komenda do sprawdzenia liczby mutów i warnów
@bot.command()
async def stats(ctx, member: discord.Member = None):
    member = member or ctx.author  # Jeśli nie podano użytkownika, sprawdzamy dane osoby wysyłającej komendę
    data = load_data()
    
    if str(member.id) not in data:
        await ctx.send(f"Brak danych dla {member.name}.")
        return
    
    mutes = data[str(member.id)]["mutes"]
    warns = data[str(member.id)]["warns"]
    
    # Liczba mutów i warnów w określonych okresach czasowych
    mutes_week = count_recent_actions(mutes, 7)
    warns_week = count_recent_actions(warns, 7)
    mutes_month = count_recent_actions(mutes, 30)
    warns_month = count_recent_actions(warns, 30)
    mutes_all_time = len(mutes)
    warns_all_time = len(warns)
    
    # Wyświetlamy muty z powodami i czasem trwania
    mute_details = "\n".join([f"- Mute z dnia {mute['timestamp']} na {mute['duration']} minut, powód: {mute['reason'] or 'Brak powodu'}"
                              for mute in mutes])
    
    warn_details = "\n".join([f"- Warn z dnia {warn['timestamp']}, powód: {warn['reason'] or 'Brak powodu'}"
                              for warn in warns])
    
    await ctx.send(f"Statystyki dla {member.name}:\n"
                   f"- Mute w tym tygodniu: {mutes_week}\n"
                   f"- Warn w tym tygodniu: {warns_week}\n"
                   f"- Mute w tym miesiącu: {mutes_month}\n"
                   f"- Warn w tym miesiącu: {warns_month}\n"
                   f"- Mute ogólnie: {mutes_all_time}\n"
                   f"- Warn ogólnie: {warns_all_time}\n\n"
                   f"**Szczegóły mutów:**\n{mute_details or 'Brak mutów'}\n\n"
                   f"**Szczegóły warnów:**\n{warn_details or 'Brak warnów'}")

# Task do sprawdzania wygasłych mutów
@bot.event
async def on_ready():
    check_mutes.start()  # Uruchamiamy task
    print(f'Zalogowano jako {bot.user}!')

def count_recent_actions(action_list, days):
    now = datetime.utcnow()
    count = 0
    for action in action_list:
        action_time = datetime.fromisoformat(action["timestamp"])
        if now - action_time <= timedelta(days=days):
            count += 1
    return count   

# Komenda /pluginy
@tree.command(name="pluginy", description="Wyświetla listę pluginów Minecraft")
async def pluginy(interaction: discord.Interaction):
    try:
        # Połączenie z RCON i pobranie listy pluginów
        with MCRcon(RCON_HOST, RCON_PASSWORD, RCON_PORT) as mcr:
            response = mcr.command("plugins")
        
        # Odpowiedź zawierająca listę pluginów
        await interaction.response.send_message(f"Zainstalowane pluginy: {response}")
    
    except Exception as e:
        await interaction.response.send_message(f"Wystąpił błąd podczas łączenia z serwerem Minecraft: {e}")

# Komenda /ban
@tree.command(name="ban-mc", description="Banuje gracza na określony czas")
@app_commands.describe(gracz="Nazwa gracza do zbanowania", czas="Czas bana w minutach")
async def ban(interaction: discord.Interaction, gracz: str, czas: int):
    try:
        # Połączenie z RCON i banowanie gracza
        with MCRcon(RCON_HOST, RCON_PASSWORD, RCON_PORT) as mcr:
            ban_command = f"ban {gracz} {czas}m"
            response = mcr.command(ban_command)
        
        # Odpowiedź na Discordzie o banie
        await interaction.response.send_message(f"Gracz {gracz} został zbanowany na {czas} minut. Komunikat serwera: {response}")
        
        # Odbanowanie po czasie
        await asyncio.sleep(czas * 60)  # czas w minutach na sekundy
        with MCRcon(RCON_HOST, RCON_PASSWORD, RCON_PORT) as mcr:
            pardon_command = f"pardon {gracz}"
            mcr.command(pardon_command)
        
        # Informacja o odbanowaniu
        await interaction.followup.send(f"Gracz {gracz} został odbanowany po {czas} minutach.")
    
    except Exception as e:
        await interaction.response.send_message(f"Wystąpił błąd podczas banowania gracza: {e}")  

bot.run('')
