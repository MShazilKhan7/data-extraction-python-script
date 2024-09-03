from playwright.sync_api import sync_playwright
from dataclasses import dataclass, asdict, field
import pandas as pd
import argparse
import os
import sys

@dataclass
class Business:
    """Holds business data."""
    name: str = None
    address: str = None
    website: str = None
    phone_number: str = None
    reviews_count: int = None
    reviews_average: float = None
    latitude: float = None
    longitude: float = None

@dataclass
class BusinessList:
    """Holds a list of Business objects and saves to both Excel and CSV."""
    business_list: list[Business] = field(default_factory=list)
    save_at: str = 'output'

    def dataframe(self):
        """Transforms business_list to pandas dataframe."""
        return pd.json_normalize(
            (asdict(business) for business in self.business_list), sep="_"
        )

    def save_to_excel(self, filename):
        """Saves pandas dataframe to an Excel (xlsx) file."""
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        self.dataframe().to_excel(f"{self.save_at}/{filename}.xlsx", index=False)

    def save_to_csv(self, filename):
        """Saves pandas dataframe to a CSV file."""
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        self.dataframe().to_csv(f"{self.save_at}/{filename}.csv", index=False)

def extract_coordinates_from_url(url: str) -> tuple[float, float]:
    """Helper function to extract coordinates from URL."""
    coordinates = url.split('/@')[-1].split('/')[0]
    latitude, longitude = coordinates.split(',')[0], coordinates.split(',')[1]
    return float(latitude), float(longitude)

def main():
    ########
    # Input 
    ########
    # Read search from arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--search", type=str)
    parser.add_argument("-t", "--total", type=int)
    args = parser.parse_args()

    if args.search:
        search_list = [args.search]
    else:
        search_list = []

    total = args.total if args.total else 1_000_000

    if not search_list:
        input_file_name = 'input.txt'
        input_file_path = os.path.join(os.getcwd(), input_file_name)
        if os.path.exists(input_file_path):
            with open(input_file_path, 'r') as file:
                search_list = file.readlines()
        if not search_list:
            print('Error: You must either pass the -s search argument, or add searches to input.txt')
            sys.exit()

    ###########
    # Scraping
    ###########
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto("https://www.google.com/maps", timeout=60000)
        page.wait_for_timeout(5000)
        
        for search_for_index, search_for in enumerate(search_list):
            print(f"-----\n{search_for_index} - {search_for}".strip())

            page.locator('//input[@id="searchboxinput"]').fill(search_for)
            page.wait_for_timeout(3000)

            page.keyboard.press("Enter")
            page.wait_for_timeout(5000)

            # Scrolling
            page.hover('//a[contains(@href, "https://www.google.com/maps/place")]')

            previously_counted = 0
            while True:
                page.mouse.wheel(0, 10000)
                page.wait_for_timeout(3000)

                locator_count = page.locator(
                    '//a[contains(@href, "https://www.google.com/maps/place")]'
                ).count()
                
                if locator_count >= total:
                    listings = page.locator(
                        '//a[contains(@href, "https://www.google.com/maps/place")]'
                    ).all()[:total]
                    listings = [listing.locator("xpath=..") for listing in listings]
                    print(f"Total Scraped: {len(listings)}")
                    break
                else:
                    if locator_count == previously_counted:
                        listings = page.locator(
                            '//a[contains(@href, "https://www.google.com/maps/place")]'
                        ).all()
                        print(f"Arrived at all available\nTotal Scraped: {len(listings)}")
                        break
                    else:
                        previously_counted = locator_count
                        print(f"Currently Scraped: {locator_count}")

            business_list = BusinessList()

            # Scraping
            for listing in listings:
                try:
                    listing.click()
                    page.wait_for_timeout(5000)

                    # name_xpath = '//div[1]/div[3]/div[8]/div[9]/div[1]/div[1]/div[1]/div[2]/div[1]/div[1]/div[1]/div[1]/div[2]/div[1]/div[1]/div[1]/h1[1]'
                    name_class = "DUwDvf lfPIob"
                    address_xpath = '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
                    website_xpath = '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
                    phone_number_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
                    review_count_xpath = '//button[@jsaction="pane.reviewChart.moreReviews"]//span'
                    reviews_average_xpath = '//div[@jsaction="pane.reviewChart.moreReviews"]//div[@role="img"]'
                    
                    business = Business()
                   
                    # if page.locator(name_xpath).count() > 0:
                    #     business.name = page.locator(name_xpath).inner_text()
                    if page.locator(f'.{name_class.replace(" ", ".")}').count() > 0:
                        business.name = page.locator(f'.{name_class.replace(" ", ".")}').inner_text()
                        # print("name",page.locator(name_class).inner_text())
                    if page.locator(address_xpath).count() > 0:
                        business.address = page.locator(address_xpath).inner_text()
                        print("address",page.locator(address_xpath).inner_text())
                    if page.locator(website_xpath).count() > 0:
                        business.website = page.locator(website_xpath).inner_text()
                        business.website = "https://www." + business.website
                    if page.locator(phone_number_xpath).count() > 0:
                        business.phone_number = page.locator(phone_number_xpath).inner_text()
                    if page.locator(review_count_xpath).count() > 0:
                        reviews_count_text = page.locator(review_count_xpath).inner_text()
                        if reviews_count_text:
                            business.reviews_count = int(reviews_count_text.split()[0].replace(',', '').strip())
                    if page.locator(reviews_average_xpath).count() > 0:
                        reviews_average_text = page.locator(reviews_average_xpath).get_attribute('aria-label')
                        if reviews_average_text:
                            business.reviews_average = float(reviews_average_text.split()[0].replace(',', '.').strip())
                    
                    business.latitude, business.longitude = extract_coordinates_from_url(page.url)

                    business_list.business_list.append(business)
                except Exception as e:
                    print(f'Error: {e}')
            
            #########
            # Output
            #########
            search_filename = f"google_maps_data_{search_for}".replace(' ', '_')
            business_list.save_to_excel(search_filename)
            business_list.save_to_csv(search_filename)

        browser.close()

if __name__ == "__main__":
    main()
