# 🔌 API Integration Guide

## Current Status

**Right now:** The app uses **mock data** to demonstrate functionality
**Goal:** Replace mock data with real retailer APIs

All the infrastructure is ready - you just need to plug in API keys and update the API call functions!

---

## 🎯 Quick Integration Checklist

### For Each Retailer:
1. [ ] Obtain API credentials
2. [ ] Add API key to environment variables
3. [ ] Update API endpoint URLs
4. [ ] Replace mock function with real API call
5. [ ] Add rate limiting
6. [ ] Test with real data

---

## 🔑 Getting API Access

### Target (RedSky API)
**Official:** https://developer.target.com/
- Apply for API access
- Get API key
- Access product and inventory endpoints

**Endpoints needed:**
- Product lookup: `/redsky_aggregations/v1/redsky/case_study_v1`
- Store inventory: `/api/v1/stores/{store_id}/products/{tcin}`

### Walmart
**Official:** https://developer.walmart.com/
- Sign up for Walmart API
- Get Consumer ID and Private Key
- Access Open API endpoints

**Endpoints needed:**
- Product search
- Store availability
- Inventory status

### Best Buy
**Official:** https://developer.bestbuy.com/
- Register for API key
- Access Products API
- Get store availability data

**Endpoints needed:**
- Products API: `/v1/products`
- Store availability: `/v1/products/{sku}/stores.json`

### Sam's Club
**Note:** Sam's Club doesn't have a public API
- May need to use web scraping (carefully, within ToS)
- Or partner API access if available

### GameStop
**Note:** GameStop doesn't have a public API
- May need to use web scraping (carefully, within ToS)
- Check for unofficial APIs

---

## 🛠️ Integration Steps

### Step 1: Add Environment Variables

In your deployment platform (Render/Railway):

```bash
TARGET_API_KEY=your_target_key_here
WALMART_CONSUMER_ID=your_walmart_id
WALMART_PRIVATE_KEY=your_walmart_key
BESTBUY_API_KEY=your_bestbuy_key_here
```

In `app.py`, load them:
```python
import os

TARGET_API_KEY = os.environ.get('TARGET_API_KEY')
WALMART_CONSUMER_ID = os.environ.get('WALMART_CONSUMER_ID')
WALMART_PRIVATE_KEY = os.environ.get('WALMART_PRIVATE_KEY')
BESTBUY_API_KEY = os.environ.get('BESTBUY_API_KEY')
```

### Step 2: Replace Mock Functions

#### Example: Target API Integration

**Current (Mock):**
```python
def check_target_inventory(self, tcin: str, store_id: Optional[str] = None, zip_code: Optional[str] = None) -> Dict:
    import random
    stock_available = random.choice([True, False, True])
    quantity = random.randint(0, 15) if stock_available else 0
    
    return {
        'retailer': 'Target',
        'item_id': tcin,
        'in_stock': stock_available,
        'quantity': quantity,
        'store_id': store_id,
        'location_type': 'store' if store_id else 'online',
        'timestamp': datetime.now().isoformat(),
        'price': 399.99
    }
```

**Updated (Real API):**
```python
def check_target_inventory(self, tcin: str, store_id: Optional[str] = None, zip_code: Optional[str] = None) -> Dict:
    headers = {
        'Authorization': f'Bearer {TARGET_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    # For online inventory
    if not store_id:
        url = f'https://api.target.com/redsky_aggregations/v1/web/plp_search_v2'
        params = {'tcin': tcin}
    # For store-specific inventory
    else:
        url = f'https://api.target.com/fulfillment_aggregator/v1/fiats/{tcin}'
        params = {'store_id': store_id, 'zip': zip_code}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Parse Target's response format
        # (exact parsing depends on API response structure)
        in_stock = data.get('available', False)
        quantity = data.get('quantity', 0)
        price = data.get('price', {}).get('current_price', 0)
        
        return {
            'retailer': 'Target',
            'item_id': tcin,
            'in_stock': in_stock,
            'quantity': quantity,
            'store_id': store_id,
            'location_type': 'store' if store_id else 'online',
            'timestamp': datetime.now().isoformat(),
            'price': price
        }
        
    except requests.exceptions.RequestException as e:
        print(f"Target API error: {e}")
        return {
            'retailer': 'Target',
            'item_id': tcin,
            'error': str(e),
            'in_stock': False,
            'quantity': 0
        }
```

#### Example: Walmart API Integration

```python
def check_walmart_inventory(self, item_id: str, store_id: Optional[str] = None, zip_code: Optional[str] = None) -> Dict:
    headers = {
        'WM_CONSUMER.ID': WALMART_CONSUMER_ID,
        'WM_SEC.KEY': WALMART_PRIVATE_KEY,
        'Accept': 'application/json'
    }
    
    url = f'https://api.walmart.com/v1/items/{item_id}'
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Parse Walmart response
        in_stock = data.get('availableOnline', False)
        quantity = data.get('stock', 0)
        price = data.get('salePrice', 0)
        
        return {
            'retailer': 'Walmart',
            'item_id': item_id,
            'in_stock': in_stock,
            'quantity': quantity,
            'store_id': store_id,
            'location_type': 'store' if store_id else 'online',
            'timestamp': datetime.now().isoformat(),
            'price': price
        }
        
    except requests.exceptions.RequestException as e:
        print(f"Walmart API error: {e}")
        return {
            'retailer': 'Walmart',
            'item_id': item_id,
            'error': str(e),
            'in_stock': False,
            'quantity': 0
        }
```

#### Example: Best Buy API Integration

```python
def check_bestbuy_inventory(self, sku: str, store_id: Optional[str] = None, zip_code: Optional[str] = None) -> Dict:
    params = {
        'apiKey': BESTBUY_API_KEY,
        'format': 'json'
    }
    
    # Store availability
    if store_id:
        url = f'https://api.bestbuy.com/v1/stores({store_id})/products/{sku}.json'
    # Online availability
    else:
        url = f'https://api.bestbuy.com/v1/products/{sku}.json'
        params['show'] = 'onlineAvailability,salePrice'
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Parse Best Buy response
        in_stock = data.get('onlineAvailability', False)
        quantity = 1 if in_stock else 0  # Best Buy often doesn't provide exact quantity
        price = data.get('salePrice', 0)
        
        return {
            'retailer': 'Best Buy',
            'item_id': sku,
            'in_stock': in_stock,
            'quantity': quantity,
            'store_id': store_id,
            'location_type': 'store' if store_id else 'online',
            'timestamp': datetime.now().isoformat(),
            'price': price
        }
        
    except requests.exceptions.RequestException as e:
        print(f"Best Buy API error: {e}")
        return {
            'retailer': 'Best Buy',
            'item_id': sku,
            'error': str(e),
            'in_stock': False,
            'quantity': 0
        }
```

### Step 3: Add Rate Limiting

Add rate limiting to avoid API throttling:

```python
import time
from collections import defaultdict

class RateLimiter:
    def __init__(self):
        self.last_call = defaultdict(float)
        self.min_interval = {
            'Target': 1.0,      # 1 second between calls
            'Walmart': 1.0,
            'Best Buy': 0.5,    # 0.5 seconds
            'Sam\'s Club': 1.0,
            'GameStop': 1.0
        }
    
    def wait_if_needed(self, retailer: str):
        now = time.time()
        last = self.last_call[retailer]
        min_interval = self.min_interval.get(retailer, 1.0)
        
        elapsed = now - last
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        
        self.last_call[retailer] = time.time()

# Add to InventoryMonitor class
rate_limiter = RateLimiter()

def check_inventory(self, item_config: Dict) -> Dict:
    retailer = item_config['retailer']
    
    # Rate limit before API call
    self.rate_limiter.wait_if_needed(retailer)
    
    # Then proceed with API call
    if retailer == 'Target':
        return self.check_target_inventory(...)
    # etc...
```

### Step 4: Add Error Handling

Implement robust error handling:

```python
def check_inventory_with_retry(self, item_config: Dict, max_retries: int = 3) -> Dict:
    for attempt in range(max_retries):
        try:
            result = self.check_inventory(item_config)
            
            # Check for API errors
            if 'error' in result:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
            
            return result
            
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            else:
                return {
                    'retailer': item_config['retailer'],
                    'item_id': item_config['item_id'],
                    'error': f'Failed after {max_retries} attempts: {str(e)}',
                    'in_stock': False,
                    'quantity': 0
                }
```

### Step 5: Update Store Search Functions

Similarly, update the `find_nearby_stores()` functions to use real APIs:

```python
def find_nearby_stores(self, retailer: str, zip_code: str, radius: int) -> List[Dict]:
    if retailer == 'Target':
        return self._find_target_stores(zip_code, radius)
    elif retailer == 'Walmart':
        return self._find_walmart_stores(zip_code, radius)
    # etc...

def _find_target_stores(self, zip_code: str, radius: int) -> List[Dict]:
    url = 'https://api.target.com/stores/v1/stores'
    params = {
        'zip': zip_code,
        'radius': radius,
        'key': TARGET_API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        stores = []
        for store in data.get('stores', []):
            stores.append({
                'store_id': store.get('id'),
                'name': f"Target Store #{store.get('id')}",
                'address': store.get('address'),
                'distance': store.get('distance', 0)
            })
        
        return stores
        
    except requests.exceptions.RequestException as e:
        print(f"Error finding Target stores: {e}")
        return []
```

---

## 🧪 Testing Your Integration

### Local Testing

1. **Set environment variables:**
   ```bash
   export TARGET_API_KEY="your_key"
   export WALMART_CONSUMER_ID="your_id"
   # etc...
   ```

2. **Test single API call:**
   ```python
   monitor = InventoryMonitor()
   result = monitor.check_target_inventory('87729478')
   print(result)
   ```

3. **Test with app:**
   ```bash
   python app.py
   ```
   Add an item and watch the logs

### Cloud Testing

1. Add environment variables in Render/Railway dashboard
2. Redeploy the app
3. Monitor logs for API calls
4. Test with real items

---

## 📊 API Response Handling

### Common Response Patterns

Most APIs return JSON like:
```json
{
  "product": {
    "id": "87729478",
    "name": "PlayStation 5",
    "availability": {
      "online": true,
      "quantity": 12,
      "stores": [
        {
          "store_id": "1234",
          "available": true,
          "quantity": 3
        }
      ]
    },
    "price": {
      "current": 499.99
    }
  }
}
```

### Parse Carefully

Different retailers structure data differently:
- **Target:** `data.product.available_to_promise_quantity`
- **Walmart:** `data.availableOnline` / `data.stock`
- **Best Buy:** `data.onlineAvailability`

Check each API's documentation for exact field names!

---

## ⚠️ Important Considerations

### Rate Limits
- **Target:** ~60 requests/minute
- **Walmart:** ~5 requests/second
- **Best Buy:** ~5 requests/second

**Solution:** Implement rate limiting (shown above)

### API Costs
Some APIs may have costs:
- Check pricing tiers
- Start with free tier
- Monitor usage

### Terms of Service
- Read each retailer's API ToS
- Don't violate usage policies
- Respect rate limits
- Don't scrape if prohibited

### Fallback Strategy
Keep mock data as fallback:
```python
def check_inventory(self, item_config: Dict) -> Dict:
    try:
        # Try real API
        return self.check_real_api(item_config)
    except Exception as e:
        # Fall back to mock data
        print(f"API failed, using mock: {e}")
        return self.check_mock_data(item_config)
```

---

## 🎯 Quick Start Priority

1. **Start with Target** (most documented API)
2. **Add Best Buy** (good public API)
3. **Add Walmart** (requires more setup)
4. **Sam's & GameStop** (may need alternative solutions)

---

## 📚 Useful Resources

- **Target API:** https://developer.target.com/
- **Walmart API:** https://developer.walmart.com/
- **Best Buy API:** https://developer.bestbuy.com/
- **Python Requests:** https://requests.readthedocs.io/
- **API Testing:** https://www.postman.com/

---

## 💡 Pro Tips

1. **Test APIs in Postman first** before coding
2. **Cache responses** to reduce API calls
3. **Log all API calls** for debugging
4. **Set reasonable timeouts** (5-10 seconds)
5. **Handle partial failures** gracefully
6. **Monitor API quotas** to avoid overages

---

## 🎉 When APIs Are Integrated

Your app will have:
✅ **Real inventory data**
✅ **Accurate stock levels**
✅ **Live price updates**
✅ **Actual store availability**
✅ **True restocking alerts**

Until then, the mock data lets you test and perfect the UI/UX! 🚀
