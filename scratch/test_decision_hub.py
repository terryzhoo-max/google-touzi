import sys
import os

# Ensure the root directory is in the sys path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.global_decision_hub import (
    get_l1_macro_state,
    get_l2_quant_signals,
    run_l3_allocator,
    run_l4_compliance_gate,
    _build_portfolio,
    _build_data_quality
)
import json

def run_diagnostics():
    print("=" * 60)
    print("  [AlphaCore] DECISION HUB DIAGNOSTICS & VERIFICATION")
    print("=" * 60)
    
    # 1. Setup Base State
    print("\n[INIT] Fetching base portfolio and data quality...")
    try:
        portfolio = _build_portfolio()
        data_quality = _build_data_quality()
        print(f"  -> Portfolio Positions: {len(portfolio.get('positions', []))} items")
        print(f"  -> Data Quality Score: {data_quality.get('data_quality_score')}")
    except Exception as e:
        print(f"[ERROR] Failed to init base state: {e}")
        return

    # 2. Test L1 Macro State
    print("\n[L1] Testing Macro State Filter...")
    try:
        l1_macro = get_l1_macro_state()
        print(f"  -> Regime: {l1_macro.get('regime')}")
        print(f"  -> VIX Level: {l1_macro.get('vix_level')}")
        print(f"  -> Max Equity Exposure: {l1_macro.get('max_equity_exposure')}")
    except Exception as e:
        print(f"[ERROR] L1 Macro Filter failed: {e}")
        return

    # 3. Test L2 Quant Signals
    print("\n[L2] Testing Quant Engine Array...")
    try:
        l2_signals = get_l2_quant_signals()
        print(f"  -> Number of engines active: {len(l2_signals)}")
        for sig in l2_signals:
             print(f"     - {sig.get('source')}: Signal {sig.get('signal')}")
    except Exception as e:
        print(f"[ERROR] L2 Quant Signals failed: {e}")
        return

    # 4. Test L3 Allocator
    print("\n[L3] Testing Allocator Engine...")
    try:
        target_weights, rationale = run_l3_allocator(l1_macro, portfolio, data_quality)
        print(f"  -> Generated Weights: {target_weights}")
        print(f"  -> Rationale: {rationale}")
    except Exception as e:
        print(f"[ERROR] L3 Allocator failed: {e}")
        return

    # 5. Test L4 Compliance Gate
    print("\n[L4] Testing Pre-Trade Compliance Gate...")
    try:
        l4_compliance = run_l4_compliance_gate(target_weights, portfolio, data_quality)
        gate_status = l4_compliance.get("gate_status")
        print(f"  -> Gate Status: {gate_status}")
        print(f"  -> Score: {l4_compliance.get('score')}")
        if l4_compliance.get('violations'):
            print(f"  -> Violations: {l4_compliance.get('violations')}")
        if l4_compliance.get('warnings'):
            print(f"  -> Warnings: {l4_compliance.get('warnings')}")
    except Exception as e:
        print(f"[ERROR] L4 Compliance Gate failed: {e}")
        return

    print("\n" + "=" * 60)
    print("  [SUCCESS] ALL L1-L4 DECISION HUB MODULES VERIFIED")
    print("=" * 60)

if __name__ == "__main__":
    run_diagnostics()
