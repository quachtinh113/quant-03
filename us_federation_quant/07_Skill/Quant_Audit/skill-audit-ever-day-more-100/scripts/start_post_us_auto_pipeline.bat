@echo off
chcp 65001 >nul
cd /d "C:\Quant_03\us_federation_quant"
echo ================================================================================
echo [SKILL AUDIT EVER DAY MORE 100$] Running Unified Audit and Launching Latest Bot...
echo ================================================================================
python "07_Skill\Quant_Audit\skill-audit-ever-day-more-100\scripts\post_us_session_auto_pipeline.py" --live-mt5 --pretty
