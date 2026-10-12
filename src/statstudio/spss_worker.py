"""Standalone stdlib-only worker, executed by IBM's bundled Python (3.10 here).

This is our integration code, not an IBM module. Never run in the MCP process:
SPSS Python and the application's Python need not have compatible ABIs.
"""
import configparser
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback


def main():
    job_file = Path(sys.argv[1]).resolve()
    job = json.loads(job_file.read_text(encoding='utf-8'))
    folder = job_file.parent
    root = Path(job['spss_home']).resolve()
    handles = [os.add_dll_directory(str(p)) for p in (root, root / 'JRE/bin') if p.is_dir()] if os.name == 'nt' else []
    os.environ['SPSS_HOME'] = str(root)
    os.environ['PATH'] = str(root) + os.pathsep + str(root / 'JRE/bin') + os.pathsep + os.environ.get('PATH', '')
    status = {'ok': False, 'analyses': [], 'python_version': sys.version, 'spss_home': str(root)}
    config = configparser.ConfigParser()
    config.read(str(root / 'spssdxcfg.ini'))
    status['spss_version'] = config.get('version', 'SpssdxVersion', fallback='unknown')
    engine = root / 'spssengine.exe'
    if engine.is_file():
        status['engine_sha256'] = hashlib.sha256(engine.read_bytes()).hexdigest()
    spss = None
    started = False
    try:
        import spss
        spss.StartSPSS()
        started = True
        spss.Submit(job['setup'])
        spss.Submit(job['spv_open'])
        for item in job['analyses']:
            record = {'id': item['id'], 'ok': False, 'commands': []}
            status['analyses'].append(record)
            try:
                # Reload for every procedure so temporary transforms cannot leak.
                spss.Submit(job['load'])
                spss.Submit(item['oms_open'])
                for command in item['commands']:
                    spss.Submit(command)
                    level = spss.GetLastErrorLevel()
                    message = spss.GetLastErrorMessage()
                    record['commands'].append({'level': level, 'message': message})
                    if level >= 3:
                        raise RuntimeError(message or 'SPSS reported an error.')
                record['ok'] = True
            except Exception as exc:
                record['error'] = str(exc)
            finally:
                spss.Submit("OMSEND TAG='analysis'.")
        spss.Submit("OMSEND TAG='viewer'.")
        status['ok'] = bool(status['analyses']) and all(x['ok'] for x in status['analyses'])
    except Exception:
        status['error'] = traceback.format_exc()
    finally:
        if started:
            try:
                spss.StopSPSS()
            except Exception as exc:
                status['shutdown_error'] = str(exc)
                status['ok'] = False
        (folder / 'worker-status.json').write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if status['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
