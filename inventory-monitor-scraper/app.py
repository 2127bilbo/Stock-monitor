from flask import Flask, render_template, request, jsonify
from datetime import datetime
import requests
import threading
import time
import json
from typing import Dict, List, Optional
import os
import re
from bs4 import BeautifulSoup
import random

app = Flask(__name__)

# In-memory storage for monitored items
monitored_items = []
item_id_counter = 0
notification_history = []

# Check intervals in seconds
CHECK_INTERVALS = {
    '1s': 1,
    '30s': 30,
    '1m': 60,
    '2m': 120,
    '5m': 300,
    '15m': 900,
    '30m': 1800,
    '1h': 3600,
    'daily': 86400
}

# Store active monitoring threads
monitoring_threads = {}

# User agent to avoid being blocked
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

class InventoryMonitor:
    """Handles inventory checking for multiple retailers via web scraping"""
    
    def __init__(self):
        self.last_check_times = {}
        self.previous_stock = {}
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
    
    def check_target_inventory(self, tcin: str, store_id: Optional[str] = None, zip_code: Optional[str] = None) -> Dict:
        """Scrape Target product page for inventory"""
        try:
            url = f'https://www.target.com/p/A-{tcin}'
            
            headers = {
                'User-Agent': USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            
            response = self.session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 404:
                return {
                    'retailer': 'Target',
                    'item_id': tcin,
                    'in_stock': False,
                    'quantity': 0,
                    'error': 'Product not found',
                    'timestamp': datetime.now().isoformat()
                }
            
            response.raise_for_status()
            html = response.text
            
            # Look for stock status in the HTML
            in_stock = False
            quantity = 0
            price = 0.0
            
            # Check for out of stock indicators
            out_of_stock_phrases = [
                'out of stock',
                'currently unavailable',
                'not available',
                'sold out',
                'Out of stock'
            ]
            
            # Check for in stock indicators
            in_stock_phrases = [
                'add to cart',
                'Add to cart',
                'in stock',
                'In stock',
                'Available',
                'available'
            ]
            
            html_lower = html.lower()
            
            # Check if product is out of stock
            is_out_of_stock = any(phrase.lower() in html_lower for phrase in out_of_stock_phrases)
            
            # Check if product is in stock
            has_add_to_cart = any(phrase.lower() in html_lower for phrase in in_stock_phrases)
            
            if not is_out_of_stock and has_add_to_cart:
                in_stock = True
                quantity = 1  # Target doesn't usually show exact quantity
            
            # Try to extract price
            price_patterns = [
                r'\$(\d+\.\d{2})',
                r'"price":(\d+\.\d{2})',
                r'price&quot;:(\d+\.\d{2})'
            ]
            
            for pattern in price_patterns:
                price_match = re.search(pattern, html)
                if price_match:
                    try:
                        price = float(price_match.group(1))
                        break
                    except:
                        pass
            
            return {
                'retailer': 'Target',
                'item_id': tcin,
                'in_stock': in_stock,
                'quantity': quantity if in_stock else 0,
                'store_id': store_id,
                'location_type': 'store' if store_id else 'online',
                'timestamp': datetime.now().isoformat(),
                'price': price if price > 0 else None
            }
            
        except requests.exceptions.RequestException as e:
            print(f"Target scraping error for {tcin}: {e}")
            return {
                'retailer': 'Target',
                'item_id': tcin,
                'in_stock': False,
                'quantity': 0,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def check_walmart_inventory(self, item_id: str, store_id: Optional[str] = None, zip_code: Optional[str] = None) -> Dict:
        """Scrape Walmart product page for inventory"""
        try:
            # Walmart uses different URL formats
            url = f'https://www.walmart.com/ip/{item_id}'
            
            headers = {
                'User-Agent': USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            
            response = self.session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 404:
                return {
                    'retailer': 'Walmart',
                    'item_id': item_id,
                    'in_stock': False,
                    'quantity': 0,
                    'error': 'Product not found',
                    'timestamp': datetime.now().isoformat()
                }
            
            response.raise_for_status()
            html = response.text
            
            in_stock = False
            quantity = 0
            price = 0.0
            
            # Walmart indicators
            out_of_stock_phrases = [
                'out of stock',
                'not available',
                'sold out',
                'Get in-stock alert'
            ]
            
            in_stock_phrases = [
                'add to cart',
                'Add to cart',
                'in stock',
                'Add to list'
            ]
            
            html_lower = html.lower()
            
            is_out_of_stock = any(phrase.lower() in html_lower for phrase in out_of_stock_phrases)
            has_add_to_cart = any(phrase.lower() in html_lower for phrase in in_stock_phrases)
            
            if not is_out_of_stock and has_add_to_cart:
                in_stock = True
                quantity = 1
            
            # Extract price
            price_patterns = [
                r'\$(\d+\.\d{2})',
                r'"price":"(\d+\.\d{2})"',
                r'price&quot;:&quot;(\d+\.\d{2})'
            ]
            
            for pattern in price_patterns:
                price_match = re.search(pattern, html)
                if price_match:
                    try:
                        price = float(price_match.group(1))
                        break
                    except:
                        pass
            
            return {
                'retailer': 'Walmart',
                'item_id': item_id,
                'in_stock': in_stock,
                'quantity': quantity if in_stock else 0,
                'store_id': store_id,
                'location_type': 'store' if store_id else 'online',
                'timestamp': datetime.now().isoformat(),
                'price': price if price > 0 else None
            }
            
        except requests.exceptions.RequestException as e:
            print(f"Walmart scraping error for {item_id}: {e}")
            return {
                'retailer': 'Walmart',
                'item_id': item_id,
                'in_stock': False,
                'quantity': 0,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def check_bestbuy_inventory(self, sku: str, store_id: Optional[str] = None, zip_code: Optional[str] = None) -> Dict:
        """Scrape Best Buy product page for inventory"""
        try:
            # Best Buy URL format
            url = f'https://www.bestbuy.com/site/{sku}.p?skuId={sku}'
            
            headers = {
                'User-Agent': USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            response = self.session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 404:
                return {
                    'retailer': 'Best Buy',
                    'item_id': sku,
                    'in_stock': False,
                    'quantity': 0,
                    'error': 'Product not found',
                    'timestamp': datetime.now().isoformat()
                }
            
            response.raise_for_status()
            html = response.text
            
            in_stock = False
            quantity = 0
            price = 0.0
            
            # Best Buy indicators
            out_of_stock_phrases = [
                'sold out',
                'coming soon',
                'unavailable nearby'
            ]
            
            in_stock_phrases = [
                'add to cart',
                'Add to Cart',
                'in stock',
                'available'
            ]
            
            html_lower = html.lower()
            
            is_out_of_stock = any(phrase.lower() in html_lower for phrase in out_of_stock_phrases)
            has_add_to_cart = any(phrase.lower() in html_lower for phrase in in_stock_phrases)
            
            if not is_out_of_stock and has_add_to_cart:
                in_stock = True
                quantity = 1
            
            # Extract price
            price_patterns = [
                r'\$(\d+\.\d{2})',
                r'"price":(\d+\.\d{2})',
            ]
            
            for pattern in price_patterns:
                price_match = re.search(pattern, html)
                if price_match:
                    try:
                        price = float(price_match.group(1))
                        break
                    except:
                        pass
            
            return {
                'retailer': 'Best Buy',
                'item_id': sku,
                'in_stock': in_stock,
                'quantity': quantity if in_stock else 0,
                'store_id': store_id,
                'location_type': 'store' if store_id else 'online',
                'timestamp': datetime.now().isoformat(),
                'price': price if price > 0 else None
            }
            
        except requests.exceptions.RequestException as e:
            print(f"Best Buy scraping error for {sku}: {e}")
            return {
                'retailer': 'Best Buy',
                'item_id': sku,
                'in_stock': False,
                'quantity': 0,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def check_sams_inventory(self, item_id: str, club_id: Optional[str] = None, zip_code: Optional[str] = None) -> Dict:
        """Scrape Sam's Club product page for inventory"""
        try:
            url = f'https://www.samsclub.com/p/{item_id}'
            
            headers = {
                'User-Agent': USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            response = self.session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 404:
                return {
                    'retailer': "Sam's Club",
                    'item_id': item_id,
                    'in_stock': False,
                    'quantity': 0,
                    'error': 'Product not found',
                    'timestamp': datetime.now().isoformat()
                }
            
            response.raise_for_status()
            html = response.text
            
            in_stock = False
            quantity = 0
            price = 0.0
            
            out_of_stock_phrases = [
                'out of stock',
                'not available',
                'sold out'
            ]
            
            in_stock_phrases = [
                'add to cart',
                'Add to cart',
                'in stock'
            ]
            
            html_lower = html.lower()
            
            is_out_of_stock = any(phrase.lower() in html_lower for phrase in out_of_stock_phrases)
            has_add_to_cart = any(phrase.lower() in html_lower for phrase in in_stock_phrases)
            
            if not is_out_of_stock and has_add_to_cart:
                in_stock = True
                quantity = 1
            
            # Extract price
            price_patterns = [
                r'\$(\d+\.\d{2})',
                r'"price":"(\d+\.\d{2})"',
            ]
            
            for pattern in price_patterns:
                price_match = re.search(pattern, html)
                if price_match:
                    try:
                        price = float(price_match.group(1))
                        break
                    except:
                        pass
            
            return {
                'retailer': "Sam's Club",
                'item_id': item_id,
                'in_stock': in_stock,
                'quantity': quantity if in_stock else 0,
                'store_id': club_id,
                'location_type': 'club' if club_id else 'online',
                'timestamp': datetime.now().isoformat(),
                'price': price if price > 0 else None
            }
            
        except requests.exceptions.RequestException as e:
            print(f"Sam's Club scraping error for {item_id}: {e}")
            return {
                'retailer': "Sam's Club",
                'item_id': item_id,
                'in_stock': False,
                'quantity': 0,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def check_gamestop_inventory(self, sku: str, store_id: Optional[str] = None, zip_code: Optional[str] = None) -> Dict:
        """Scrape GameStop product page for inventory"""
        try:
            # GameStop URL format
            url = f'https://www.gamestop.com/product/{sku}'
            
            headers = {
                'User-Agent': USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            response = self.session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 404:
                return {
                    'retailer': 'GameStop',
                    'item_id': sku,
                    'in_stock': False,
                    'quantity': 0,
                    'error': 'Product not found',
                    'timestamp': datetime.now().isoformat()
                }
            
            response.raise_for_status()
            html = response.text
            
            in_stock = False
            quantity = 0
            price = 0.0
            
            out_of_stock_phrases = [
                'not available',
                'unavailable',
                'out of stock'
            ]
            
            in_stock_phrases = [
                'add to cart',
                'Add to Cart',
                'in stock',
                'available'
            ]
            
            html_lower = html.lower()
            
            is_out_of_stock = any(phrase.lower() in html_lower for phrase in out_of_stock_phrases)
            has_add_to_cart = any(phrase.lower() in html_lower for phrase in in_stock_phrases)
            
            if not is_out_of_stock and has_add_to_cart:
                in_stock = True
                quantity = 1
            
            # Extract price
            price_patterns = [
                r'\$(\d+\.\d{2})',
                r'"price":"(\d+\.\d{2})"',
            ]
            
            for pattern in price_patterns:
                price_match = re.search(pattern, html)
                if price_match:
                    try:
                        price = float(price_match.group(1))
                        break
                    except:
                        pass
            
            return {
                'retailer': 'GameStop',
                'item_id': sku,
                'in_stock': in_stock,
                'quantity': quantity if in_stock else 0,
                'store_id': store_id,
                'location_type': 'store' if store_id else 'online',
                'timestamp': datetime.now().isoformat(),
                'price': price if price > 0 else None
            }
            
        except requests.exceptions.RequestException as e:
            print(f"GameStop scraping error for {sku}: {e}")
            return {
                'retailer': 'GameStop',
                'item_id': sku,
                'in_stock': False,
                'quantity': 0,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def check_inventory(self, item_config: Dict) -> Dict:
        """Check inventory based on retailer"""
        retailer = item_config['retailer']
        item_id = item_config['item_id']
        store_id = item_config.get('store_id')
        zip_code = item_config.get('zip_code')
        
        # Add delay to avoid rate limiting
        time.sleep(random.uniform(1, 3))
        
        if retailer == 'Target':
            return self.check_target_inventory(item_id, store_id, zip_code)
        elif retailer == 'Walmart':
            return self.check_walmart_inventory(item_id, store_id, zip_code)
        elif retailer == 'Best Buy':
            return self.check_bestbuy_inventory(item_id, store_id, zip_code)
        elif retailer == "Sam's Club":
            return self.check_sams_inventory(item_id, store_id, zip_code)
        elif retailer == 'GameStop':
            return self.check_gamestop_inventory(item_id, store_id, zip_code)
        else:
            return {'error': f'Unknown retailer: {retailer}'}
    
    def find_nearby_stores(self, retailer: str, zip_code: str, radius: int) -> List[Dict]:
        """Find stores near a zip code - mock data for now"""
        # Store locator scraping would be complex and site-specific
        # Using mock data for store locations
        mock_stores = []
        
        if retailer == 'Target':
            mock_stores = [
                {'store_id': 'T1234', 'name': 'Target Store #1234', 'address': '123 Main St', 'distance': 2.5},
                {'store_id': 'T5678', 'name': 'Target Store #5678', 'address': '456 Oak Ave', 'distance': 5.8},
                {'store_id': 'T9012', 'name': 'Target Store #9012', 'address': '789 Pine Rd', 'distance': 8.2}
            ]
        elif retailer == 'Walmart':
            mock_stores = [
                {'store_id': 'W2345', 'name': 'Walmart Supercenter #2345', 'address': '234 Commerce Dr', 'distance': 3.1},
                {'store_id': 'W6789', 'name': 'Walmart Supercenter #6789', 'address': '567 Market St', 'distance': 7.4}
            ]
        elif retailer == 'Best Buy':
            mock_stores = [
                {'store_id': 'BB123', 'name': 'Best Buy #123', 'address': '345 Tech Plaza', 'distance': 4.2},
                {'store_id': 'BB456', 'name': 'Best Buy #456', 'address': '678 Electronics Way', 'distance': 9.5}
            ]
        elif retailer == "Sam's Club":
            mock_stores = [
                {'store_id': 'SC789', 'name': "Sam's Club #789", 'address': '890 Warehouse Blvd', 'distance': 6.3}
            ]
        elif retailer == 'GameStop':
            mock_stores = [
                {'store_id': 'GS111', 'name': 'GameStop #111', 'address': '111 Mall Dr', 'distance': 1.8},
                {'store_id': 'GS222', 'name': 'GameStop #222', 'address': '222 Plaza Circle', 'distance': 4.7},
                {'store_id': 'GS333', 'name': 'GameStop #333', 'address': '333 Shopping Center', 'distance': 8.9}
            ]
        
        return [store for store in mock_stores if store['distance'] <= radius]

# Initialize monitor
inventory_monitor = InventoryMonitor()

def monitor_item_loop(item: Dict):
    """Background thread to continuously monitor an item"""
    item_key = f"{item['id']}"
    
    while item_key in monitoring_threads and monitoring_threads[item_key].get('active', False):
        try:
            # Check inventory
            result = inventory_monitor.check_inventory(item)
            
            # Update item status
            for monitored in monitored_items:
                if monitored['id'] == item['id']:
                    previous_quantity = monitored.get('current_quantity', 0)
                    current_quantity = result.get('quantity', 0)
                    
                    monitored['last_check'] = datetime.now().isoformat()
                    monitored['in_stock'] = result.get('in_stock', False)
                    monitored['current_quantity'] = current_quantity
                    monitored['price'] = result.get('price')
                    
                    # Store any errors
                    if 'error' in result:
                        monitored['last_error'] = result['error']
                    else:
                        monitored['last_error'] = None
                    
                    # Detect stock changes (0 to any positive number)
                    if previous_quantity == 0 and current_quantity > 0:
                        notification = {
                            'id': len(notification_history) + 1,
                            'timestamp': datetime.now().isoformat(),
                            'item_name': monitored['item_name'],
                            'retailer': monitored['retailer'],
                            'quantity': current_quantity,
                            'location_type': monitored.get('location_type', 'online'),
                            'store_id': monitored.get('store_id'),
                            'price': monitored.get('price'),
                            'message': f"🎉 {monitored['item_name']} is NOW IN STOCK at {monitored['retailer']}! Quantity: {current_quantity}"
                        }
                        notification_history.insert(0, notification)
                        
                        # Keep only last 50 notifications
                        if len(notification_history) > 50:
                            notification_history.pop()
                    
                    break
            
            # Wait for the specified interval
            interval = item.get('check_interval', '2m')
            sleep_time = CHECK_INTERVALS.get(interval, 120)
            time.sleep(sleep_time)
            
        except Exception as e:
            print(f"Error monitoring item {item['id']}: {e}")
            time.sleep(60)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/retailers')
def get_retailers():
    """Get list of supported retailers"""
    retailers = [
        {'id': 'target', 'name': 'Target'},
        {'id': 'walmart', 'name': 'Walmart'},
        {'id': 'bestbuy', 'name': 'Best Buy'},
        {'id': 'sams', 'name': "Sam's Club"},
        {'id': 'gamestop', 'name': 'GameStop'}
    ]
    return jsonify(retailers)

@app.route('/api/intervals')
def get_intervals():
    """Get available check intervals"""
    intervals = [
        {'id': '1s', 'name': 'Every Second (⚠️ High Load)', 'seconds': 1},
        {'id': '30s', 'name': 'Every 30 Seconds', 'seconds': 30},
        {'id': '1m', 'name': 'Every Minute', 'seconds': 60},
        {'id': '2m', 'name': 'Every 2 Minutes', 'seconds': 120},
        {'id': '5m', 'name': 'Every 5 Minutes', 'seconds': 300},
        {'id': '15m', 'name': 'Every 15 Minutes', 'seconds': 900},
        {'id': '30m', 'name': 'Every 30 Minutes', 'seconds': 1800},
        {'id': '1h', 'name': 'Every Hour', 'seconds': 3600},
        {'id': 'daily', 'name': 'Once Daily', 'seconds': 86400}
    ]
    return jsonify(intervals)

@app.route('/api/stores/search', methods=['POST'])
def search_stores():
    """Find stores near a zip code"""
    data = request.json
    retailer = data.get('retailer')
    zip_code = data.get('zip_code')
    radius = data.get('radius', 10)
    
    stores = inventory_monitor.find_nearby_stores(retailer, zip_code, radius)
    return jsonify({'stores': stores})

@app.route('/api/monitor/add', methods=['POST'])
def add_monitor():
    """Add an item to monitor"""
    global item_id_counter
    
    data = request.json
    item_id_counter += 1
    
    new_item = {
        'id': item_id_counter,
        'retailer': data.get('retailer'),
        'item_id': data.get('item_id'),
        'item_name': data.get('item_name'),
        'location_type': data.get('location_type', 'online'),
        'store_id': data.get('store_id'),
        'store_name': data.get('store_name'),
        'zip_code': data.get('zip_code'),
        'check_interval': data.get('check_interval', '2m'),
        'added_at': datetime.now().isoformat(),
        'last_check': None,
        'in_stock': False,
        'current_quantity': 0,
        'price': None,
        'last_error': None
    }
    
    monitored_items.append(new_item)
    
    # Start monitoring thread
    thread = threading.Thread(target=monitor_item_loop, args=(new_item,), daemon=True)
    monitoring_threads[f"{new_item['id']}"] = {'thread': thread, 'active': True}
    thread.start()
    
    return jsonify({'success': True, 'item': new_item})

@app.route('/api/monitor/remove/<int:item_id>', methods=['DELETE'])
def remove_monitor(item_id):
    """Remove an item from monitoring"""
    global monitored_items
    
    # Stop monitoring thread
    item_key = f"{item_id}"
    if item_key in monitoring_threads:
        monitoring_threads[item_key]['active'] = False
        del monitoring_threads[item_key]
    
    # Remove from list
    monitored_items = [item for item in monitored_items if item['id'] != item_id]
    
    return jsonify({'success': True})

@app.route('/api/monitor/list')
def list_monitors():
    """Get all monitored items"""
    return jsonify({'items': monitored_items})

@app.route('/api/monitor/check/<int:item_id>', methods=['POST'])
def check_item_now(item_id):
    """Manually check an item immediately"""
    for item in monitored_items:
        if item['id'] == item_id:
            result = inventory_monitor.check_inventory(item)
            
            # Update item
            item['last_check'] = datetime.now().isoformat()
            item['in_stock'] = result.get('in_stock', False)
            item['current_quantity'] = result.get('quantity', 0)
            item['price'] = result.get('price')
            
            if 'error' in result:
                item['last_error'] = result['error']
            else:
                item['last_error'] = None
            
            return jsonify({'success': True, 'result': result})
    
    return jsonify({'success': False, 'error': 'Item not found'}), 404

@app.route('/api/monitor/check-all', methods=['POST'])
def check_all_items():
    """Manually check all items immediately"""
    results = []
    
    for item in monitored_items:
        result = inventory_monitor.check_inventory(item)
        
        item['last_check'] = datetime.now().isoformat()
        item['in_stock'] = result.get('in_stock', False)
        item['current_quantity'] = result.get('quantity', 0)
        item['price'] = result.get('price')
        
        if 'error' in result:
            item['last_error'] = result['error']
        else:
            item['last_error'] = None
        
        results.append({
            'item_id': item['id'],
            'item_name': item['item_name'],
            'in_stock': item['in_stock'],
            'quantity': item['current_quantity']
        })
    
    return jsonify({'success': True, 'results': results})

@app.route('/api/notifications')
def get_notifications():
    """Get recent notifications"""
    return jsonify({'notifications': notification_history[:20]})

@app.route('/api/stats')
def get_stats():
    """Get monitoring statistics"""
    total_items = len(monitored_items)
    in_stock_items = sum(1 for item in monitored_items if item.get('in_stock', False))
    out_of_stock = total_items - in_stock_items
    
    retailers_count = {}
    for item in monitored_items:
        retailer = item['retailer']
        retailers_count[retailer] = retailers_count.get(retailer, 0) + 1
    
    return jsonify({
        'total_items': total_items,
        'in_stock': in_stock_items,
        'out_of_stock': out_of_stock,
        'retailers': retailers_count,
        'total_notifications': len(notification_history)
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
