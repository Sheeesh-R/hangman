import random
import csv
import json
import google.generativeai as genai
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme
from rich.progress import Progress, BarColumn, TextColumn

# Configure terminal styling with rich library
# Define custom color theme for different message types (success, error, etc.)
custom_theme = Theme({
    "title": "bold cyan",
    "success": "bold green",
    "error": "bold red",
    "warning": "bold yellow"
})
console = Console(theme=custom_theme)

# Gemini API configuration
GEMINI_API_KEY = "AIzaSyBxcRnT5J8Okhai4hU0XJmEw8F3qCP9dZI"
genai.configure(api_key=GEMINI_API_KEY)

def load_words():
    """
    Load predefined word lists categorized by difficulty from a JSON file.
    
    Structure of wordlist.json:
    {
        "easy": ["simple", "words", ...],
        "medium": ["average", "difficulty", ...],
        "hard": ["challenging", "vocabulary", ...]
    }
    
    Returns:
        dict: Dictionary containing word lists for each difficulty level
              Default empty lists if file not found
    """
    word_dict = {"easy": [], "medium": [], "hard": []}
    try:
        with open("wordlist.json", "r") as file:
            word_dict = json.load(file)
    except FileNotFoundError:
        console.print("[warning]wordlist.json not found. Using default words.[/warning]")
    return word_dict

def load_custom_words():
    """
    Load user-defined custom words from a CSV file.
    
    Expected format: Single column CSV with one word per row.
    Words will be normalized to lowercase for game consistency.
    
    Returns:
        list: List of custom words, or empty list if file not found or empty
    """
    try:
        with open("words.csv", "r") as file:
            reader = csv.reader(file)
            customWords = [row[0].strip().lower() for row in reader if row]
            if not customWords:
                console.print("[warning]Custom word list is empty.[/warning]")
                return []
            return customWords
    except FileNotFoundError:
        console.print("[warning]Custom words file not found.[/warning]")
        return []

def get_word_by_difficulty(difficulty, word_dict, custom_words):
    """
    Select a random word based on chosen difficulty level.
    
    Parameters:
        difficulty (str): Selected difficulty level ("easy", "medium", "hard", "custom")
        word_dict (dict): Dictionary containing word lists for each difficulty
        custom_words (list): List of user-provided custom words
    
    Returns:
        str: Randomly selected word for the game
             Fallback words provided if selected difficulty has no words
    """
    if difficulty == "custom":
        # Return random custom word or default if custom list is empty
        return random.choice(custom_words) if custom_words else "ocean"
    else:
        # Get words for selected difficulty with empty list fallback
        words = word_dict.get(difficulty, [])
        return random.choice(words) if words else "default"

def generate_hint(secretWord):
    """
    Generate a contextual hint for the secret word using Gemini AI.
    
    Creates a prompt that requests a hint without revealing the word directly.
    Uses Gemini 2.0 Flash model to generate context-aware hints.
    
    Parameters:
        secretWord (str): The word the player is trying to guess
    
    Returns:
        str: AI-generated hint about the word, or fallback hint on API error
    """
    # Construct prompt with careful instructions to avoid revealing the word
    prompt = f"Provide a helpful hint for the word '{secretWord}' without giving away the full word. The hint could be the starting letter, a synonym, a simple definition or a related word. Create the hint without using the original word in the hint."
    try:
        # Initialize Gemini model and generate response
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        # Provide fallback hint if API call fails
        console.print(f"[error]Error generating hint: {str(e)}[/error]")
        return "This word has something to do with its definition."

def get_lives_for_difficulty(difficulty):
    """
    Determine the number of lives (allowed incorrect guesses) based on difficulty.
    
    Parameters:
        difficulty (str): Selected game difficulty
    
    Returns:
        int: Number of lives for the selected difficulty
             Default to 5 lives for unknown difficulty values
    """
    lives_dict = {"easy": 7, "medium": 5, "hard": 3, "custom": 6}
    return lives_dict.get(difficulty, 5)

def hangman():
    """
    Main game function that manages the entire Hangman gameplay loop.
    
    Features:
    - Difficulty selection with varying lives
    - Word selection from different word lists
    - Progressive hint system that activates after losing lives
    - Dynamic scoring based on correct/incorrect guesses and hints used
    - Visual progress tracking of word completion
    - Full word guess capability
    - Replay option
    
    Game ends when player guesses the word or runs out of lives.
    """
    # Game introduction and welcome screen
    console.print(Panel.fit("Welcome To Hangman", title="🎮 Game Start", border_style="cyan"))
    console.print("You have limited tries to guess your word based on difficulty.", style="italic")
    console.print("Type '0' at any time to exit the game.", style="italic")

    # Load word lists from external files
    word_dict = load_words()
    customWords = load_custom_words()

    # Display difficulty options with their characteristics
    console.print("\nChoose your difficulty level:", style="bold")
    console.print("  1. Easy   - More common words, 7 lives")
    console.print("  2. Medium - Standard words, 5 lives")
    console.print("  3. Hard   - Challenging words, 3 lives")
    console.print("  4. Custom - Words from your custom list, 6 lives")
    
    # Difficulty selection loop - continues until valid choice or exit
    while True:
        difficulty_input = console.input("\n[bold]Enter difficulty (1-4 or name, or '0' to exit): [/bold]").lower()

        # Exit game if requested
        if difficulty_input == "0":
            console.print("\n[warning]Exiting the game. Thanks for playing![/warning]")
            return

        # Map numeric inputs to difficulty names for flexibility
        difficulty_map = {"1": "easy", "2": "medium", "3": "hard", "4": "custom"}
        difficulty = difficulty_map.get(difficulty_input, difficulty_input)

        # Validate difficulty selection
        if difficulty in ["easy", "medium", "hard", "custom"]:
            break
        console.print("[error]Invalid difficulty. Please choose 1-4 or type Easy, Medium, Hard, or Custom.[/error]")

    # Fallback to medium if custom selected but no custom words available
    if difficulty == "custom" and not customWords:
        console.print("[warning]No custom words available. Defaulting to Medium difficulty.[/warning]")
        difficulty = "medium"

    # Game initialization: select word and create masked version
    secretWord = get_word_by_difficulty(difficulty, word_dict, customWords)
    guessedWord = "_" * len(secretWord)  # Create placeholder with underscores

    # Set up game parameters based on difficulty
    lives = get_lives_for_difficulty(difficulty)
    maxLives = lives  # Store initial lives for reference
    guessedLetters = set()  # Track unique guessed letters
    score = 100  # Starting score
    
    # Hint system configuration
    # Hints are offered after losing multiple lives since last hint
    last_hint_lives = maxLives  # Track when last hint was offered
    hints_used = 0  # Count hints used for scoring penalty
    max_hints = 3   # Limit total available hints
    
    # Configure visual progress bar for word completion tracking
    progress_columns = [
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=20),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ]

    # Main game loop - continues until word guessed or lives depleted
    while lives > 0 and guessedWord != secretWord:
        console.print("\n" + "~" * 50)  # Visual separator
        
        # Create and display word completion progress bar
        # Shows percentage of letters revealed so far
        with Progress(*progress_columns, console=console) as progress:
            word_task = progress.add_task(
                "[green]Word Completion", 
                total=len(secretWord), 
                completed=len(secretWord) - guessedWord.count('_')
            )
            
            # Show current state of the word with spaces between letters
            display_word = ' '.join(guessedWord)
            console.print(f"Word: {display_word}", style="bold")
        
        # Visual representation of remaining lives using heart emojis
        lives_text = Text()
        for _ in range(lives):
            lives_text.append("❤️ ", style="red")
        console.print("Lives: ", end="")
        console.print(lives_text)
        
        # Display current score
        console.print(f"Score: {score}", style="bold")

        # Show letters already guessed to help player's strategy
        if guessedLetters:
            console.print(f"Letters guessed: {', '.join(sorted(guessedLetters))}", style="dim")
        else:
            console.print("No letters guessed yet", style="dim")

        # Hint system: offer hint after player loses 2 lives since last hint
        # Limited to max_hints total per game with score penalty
        if (last_hint_lives - lives >= 2) and (hints_used < max_hints):
            console.print("\nYou've lost 2 lives since your last hint offer.", style="italic")
            hint_choice = console.input("Would you like a hint? (y/n, or '0' to exit): ").lower()
            
            # Handle exit request
            if hint_choice == "0":
                console.print("\n[warning]Exiting the game. Thanks for playing![/warning]")
                return

            # Generate AI hint if player accepts offer
            if hint_choice.startswith('y'):
                hint = generate_hint(secretWord)
                console.print(f"\n[bold]Hint:[/bold] {hint}", style="yellow")
                hints_used += 1
                score -= 5  # Small score penalty for using hint
            
            # Reset hint tracking - next hint offered after 2 more lost lives
            last_hint_lives = lives

        # Get player input: single letter, full word, or exit
        guess = console.input("\n[bold]Guess a letter or the entire word (or '0' to exit): [/bold]").lower()

        # Handle exit request
        if guess == "0":
            console.print("\n[warning]Exiting the game. Thanks for playing![/warning]")
            return

        # Handle full word guess - match length of secret word
        if len(guess) == len(secretWord) and guess.isalpha():  
            if guess == secretWord:
                # Correct word guess - wins game immediately
                guessedWord = secretWord
                score += 50  # Bonus points for guessing full word
                break
            else:
                # Incorrect word guess - penalty
                console.print("[error]❌ Incorrect word guess.[/error]")
                lives -= 1
                score -= 10
                continue

        # Validate single letter input
        elif len(guess) != 1 or not guess.isalpha():
            console.print("[error]Please enter a single valid letter or the full word.[/error]")
            continue

        # Prevent duplicate letter guesses
        if guess in guessedLetters:
            console.print("[warning]You already guessed that letter. Try again.[/warning]")
            continue

        # Add valid guess to tracking set
        guessedLetters.add(guess)

        # Process correct letter guess
        if guess in secretWord:
            console.print("[success]✓ Good guess![/success]")
            # Update guessed word to reveal all instances of the guessed letter
            guessedWord = "".join([letter if letter in guessedLetters or letter == guess else "_" for letter in secretWord])
            score += 10  # Points for correct letter
        else:
            # Process incorrect letter guess
            lives -= 1
            score -= 10  # Penalty for wrong guess
            console.print("[error]❌ Incorrect guess.[/error]")

    # Game conclusion - win or lose
    console.print("\n" + "=" * 50)  # Visual separator
    
    # Win condition: all letters revealed
    if guessedWord == secretWord:
        console.print(Panel.fit("🎉 Congratulations! 🎉", title="Game Won", border_style="green"))
        console.print(f"You've guessed the word: {secretWord}", style="bold")
        console.print(f"Your final score is: {score}", style="bold")
    else:
        # Lose condition: out of lives
        score = 0  # Reset score to 0 on loss
        console.print(Panel.fit("Game Over", title="❌ Failure ❌", border_style="red"))
        console.print(f"The word was: {secretWord}", style="bold")
        console.print(f"Your final score is: {score}", style="bold")

    # Offer replay option
    playAgain = console.input("\nWould you like to play again? (y/n, or '0' to exit): ").lower()
    
    if playAgain == "0":
        console.print("\n[warning]Exiting the game. Thanks for playing![/warning]")
        return
    elif playAgain.startswith('y'):
        # Recursive call to restart the game
        hangman()
    else:
        console.print("\n[warning]Thanks for playing![/warning]")

# Entry point of the program
# Ensures game only starts when script is run directly, not when imported
if __name__ == "__main__":
    hangman()