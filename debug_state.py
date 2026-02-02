
import json
import os

try:
    with open('L:/ORA_State/cost_state.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    uh = data.get('user_history', {})
    print(f'Total Users in History: {len(uh)}')
    
    if uh:
        uid = list(uh.keys())[0]
        print(f'Sample User ID: {uid}')
        
        user_data = uh[uid]
        print(f'Lanes for User: {list(user_data.keys())}')
        
        if user_data:
            lane = list(user_data.keys())[0]
            buckets = user_data[lane]
            print(f'Bucket Count for {lane}: {len(buckets)}')
            if buckets:
                print(f'First Bucket Day: {buckets[0].get("day")}')
                print(f'Last Bucket Day: {buckets[-1].get("day")}')

    # Also check user_buckets vs user_history overlapping
    ub = data.get('user_buckets', {})
    print(f'Total Users in Active Buckets: {len(ub)}')

except Exception as e:
    print(f"Error: {e}")
