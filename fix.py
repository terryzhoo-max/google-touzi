with open('core/cache_store.py', 'r', encoding='utf-8') as f:
    text = f.read()

cached_async_code = '''
def cached_async(ttl: int, key: str):
    def decorator(fn):
        import functools, asyncio, time
        from core.db_layer import save_api_cache, get_api_cache
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            now = time.time()
            payload, updated_at = get_api_cache(key)
            if payload and (now - updated_at < ttl):
                _stats["hits"] += 1
                return payload
            
            _stats["misses"] += 1
            
            async def background_refresh():
                async with _async_locks[key]:
                    _, last_update = get_api_cache(key)
                    if time.time() - last_update < ttl: return
                    try:
                        result = await fn(*args, **kwargs)
                        if not _is_logic_error(result):
                            _stats["refreshes"] += 1
                            save_api_cache(key, result)
                    except Exception as exc:
                        _stats["errors"] += 1
                        print(f"[cache_store] Async Sync Exception {key}: {exc}")
                        
            # Execute background without waiting
            asyncio.create_task(background_refresh())
            
            if payload:
                _stats["stale_served"] += 1
                return payload
            return {"status": "syncing", "message": "Initial data sync in progress. Please refresh."}
        return wrapper
    return decorator
'''

if 'def cached_async' not in text:
    text += '\n' + cached_async_code
    with open('core/cache_store.py', 'w', encoding='utf-8') as f:
        f.write(text)

with open('data_engine.py', 'r', encoding='utf-8') as f:
    de_text = f.read()

de_text = de_text.replace('from core.cache_store import cached\n', 'from core.cache_store import cached, cached_async\n')

import re
lines = de_text.split('\n')
for i, l in enumerate(lines):
    if '@cached' in l and i+1 < len(lines):
        if 'async def ' in lines[i+1]:
            lines[i] = lines[i].replace('@cached(', '@cached_async(')

de_text = '\n'.join(lines)
with open('data_engine.py', 'w', encoding='utf-8') as f:
    f.write(de_text)

print('Restored cached_async')
