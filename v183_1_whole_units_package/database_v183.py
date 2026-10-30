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
 from django.utils import timezone as tz
 rows=exclude_elapsed(ReservationItem.objects.filter(reservation__status__in=['pending','confirmed'],reservation__check_out__gt=tz.localdate())).order_by('room_id','reservation__check_in').values_list('room_id','reservation_id','reservation__check_in','reservation__check_out')
 active={}
 for room,reservation,arrival,departure in rows:
  active[room]=[x for x in active.get(room,[]) if x[1]>arrival]
  if any(other!=reservation for other,end in active[room]):raise RuntimeError(f'Room #{room} has overlapping future reservations. Resolve these before deploying whole-unit booking; no rows are automatically removed.')
  active[room].append((reservation,departure))
 for command in ['pg_dump','pg_restore']:
  if not shutil.which(command):raise RuntimeError(command+' must be installed before deployment.')
 print('Future whole-unit inventory check passed. Saved room-price amounts will NOT be multiplied by capacity.')

def backup():
 check();folder=root/'summitdesk_backups'
 if folder.is_symlink():raise RuntimeError('Symlink backup directory refused.')
 folder.mkdir(mode=0o700,exist_ok=True)
 path=folder/('whole_units_v183_database_'+datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f'));path.mkdir(mode=0o700)
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
 (path/'manifest.json').write_text(json.dumps({'sha256':digest.hexdigest(),'database':connection.settings_dict['NAME'],'purpose':'Pre-v183 full PostgreSQL archive; no source or media files'},indent=2)+'\n')
 print('Database backup:',path)

def rollback_check():
 with connection.cursor() as cursor:
  fields={f.name for f in connection.introspection.get_table_description(cursor,'bookings_reservationitem')}
  if 'pricing_unit' in fields:
   cursor.execute("SELECT COUNT(*) FROM bookings_reservationitem WHERE pricing_unit = 'room'")
   if cursor.fetchone()[0]:raise RuntimeError('Whole-unit reservations exist. Old source would recalculate their prices incorrectly. Source rollback refused; keep v183 or arrange a reviewed database recovery.')
 print('Whole-unit source rollback guard passed.')

try:
 {'--check':check,'--backup':backup,'--rollback-check':rollback_check}[sys.argv[1]]()
except Exception as e:
 print('v183 database check stopped: '+str(e),file=sys.stderr);sys.exit(1)
