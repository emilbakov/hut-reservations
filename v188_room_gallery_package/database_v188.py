#!/usr/bin/env python3
"""Preflight/backup only. Never changes or deletes reservation rows."""
import os,sys,json,subprocess,shutil,hashlib
from pathlib import Path
from datetime import datetime,timezone
root=Path.cwd().resolve();sys.path.insert(0,str(root));os.umask(0o077)
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings_postgres')
import django
django.setup()
from django.db import connection
from bookings.models import ReservationItem,Room
from bookings.deposit_flow_v180 import exclude_elapsed

def check():
 if connection.vendor!='postgresql':raise RuntimeError('Production PostgreSQL settings are required.')
 for command in ['pg_dump','pg_restore']:
  if not shutil.which(command):raise RuntimeError(command+' must be installed before deployment.')
 print('PostgreSQL backup tools available. No reservation data will be changed by deployment.')

def backup():
 check();folder=root/'summitdesk_backups'
 if folder.is_symlink():raise RuntimeError('Symlink backup directory refused.')
 folder.mkdir(mode=0o700,exist_ok=True)
 path=folder/('room_gallery_v188_database_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f'));path.mkdir(mode=0o700)
 dump=path/'database.dump';env={k:v for k,v in os.environ.items() if not k.startswith('PG')}
 for a,b in {'dbname':'PGDATABASE','user':'PGUSER','password':'PGPASSWORD','host':'PGHOST','port':'PGPORT','sslmode':'PGSSLMODE'}.items():
  if a in connection.get_connection_params():env[b]=str(connection.get_connection_params()[a])
 env['PGCONNECT_TIMEOUT']='15'
 for args in [['pg_dump','--format=custom','--file='+str(dump)],['pg_restore','--list',str(dump)]]:
  result=subprocess.run(args,env=env,capture_output=True,timeout=600)
  if result.returncode:raise RuntimeError(Path(args[0]).name+' failed. Database upgrade has not started.')
  if args[0]=='pg_restore' and b'TABLE DATA' not in result.stdout:raise RuntimeError('Archive contains no table data; upgrade refused.')
 os.chmod(dump,0o600)
 digest=hashlib.sha256()
 with dump.open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
  os.fsync(stream.fileno())
 (path/'manifest.json').write_text(json.dumps({'sha256':digest.hexdigest(),'database':connection.settings_dict['NAME'],'purpose':'Pre-v188 full PostgreSQL archive; no source or media files'},indent=2)+'\n')
 print('Database backup:',path)



def rollback_check():
 if connection.vendor!='postgresql':raise RuntimeError('Production PostgreSQL settings are required.')
 if 'bookings_roomphoto' not in connection.introspection.table_names():
  print('Gallery migration is not applied. Previous source can be restored.');return
 from bookings.models import RoomPhoto
 if RoomPhoto.objects.exists():
  raise RuntimeError('Additional gallery photo records exist. Previous source cannot manage their room relationships. Source rollback refused to preserve them; keep v188 and fix forward. No records or files were deleted.')
 print('No additional gallery records exist; v187 source can be restored. Main room photos remain supported.')


try:
 {'--check':check,'--backup':backup,'--rollback-check':rollback_check}[sys.argv[1]]()
except Exception as e:
 print('v188 database check stopped: '+str(e),file=sys.stderr);sys.exit(1)
