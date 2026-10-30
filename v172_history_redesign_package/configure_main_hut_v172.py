#!/usr/bin/env python3
"""Choose the one hut shown at / and allowed to accept public requests."""
import argparse
import os
from pathlib import Path
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,default=Path.cwd())
    parser.add_argument('--hut',help='Exact active hut slug; useful for a non-interactive deployment.')
    parser.add_argument('--check',action='store_true',help='Show the configured main hut without writing.')
    args=parser.parse_args()
    project=args.project.resolve()
    if not (project/'manage.py').is_file():parser.error('Run beside manage.py, or supply --project.')
    sys.path.insert(0,str(project))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings_postgres')
    import django
    django.setup()
    from django.db import transaction
    from bookings.models import Hut,PublicWebsiteSettings
    huts=list(Hut.objects.filter(is_active=True).order_by('name','pk'))
    profile=PublicWebsiteSettings.objects.select_related('main_hut').filter(pk=1).first()
    current=profile.main_hut if profile and profile.main_hut_id and profile.main_hut.is_active else None
    if args.check:
        if not current:
            print('No active main hut is explicitly configured. Run this helper or select Main hut in Admin > Public website settings.')
            return 2
        print(f'Main hut: {current.name} [{current.slug}]. Other huts are information-only on the public website.')
        return 0
    selected=next((hut for hut in huts if hut.slug==args.hut),None) if args.hut else current
    if args.hut and selected is None:parser.error('The supplied slug is not an active hut.')
    if selected is None:
        if not huts:parser.error('No active hut exists. Add one in Admin, then rerun deployment.')
        if len(huts)==1:
            selected=huts[0]
        else:
            print('\nChoose the MAIN hut. It will open at / and will be the only hut accepting public reservation requests.')
            for number,hut in enumerate(huts,1):print(f'  {number}. {hut.name} [{hut.slug}]')
            if not sys.stdin.isatty():parser.error('No main hut is set. Run interactively, pass --hut SLUG, or choose Main hut in Admin before rerunning deployment.')
            while selected is None:
                choice=input('Main hut number (q to stop): ').strip()
                if choice.casefold()=='q':return 2
                if choice.isdecimal() and 1<=int(choice)<=len(huts):selected=huts[int(choice)-1]
                else:print('Enter one of the listed numbers.')
    with transaction.atomic():
        profile,_created=PublicWebsiteSettings.objects.get_or_create(pk=1)
        profile=PublicWebsiteSettings.objects.select_for_update().get(pk=profile.pk)
        selected=Hut.objects.select_for_update().filter(pk=selected.pk,is_active=True).first()
        if selected is None:parser.error('That hut is no longer active. Rerun to select a main hut.')
        if profile.main_hut_id!=selected.pk:
            profile.main_hut=selected
            profile.save(update_fields=['main_hut','updated_at'])
    print(f'Main hut: {selected.name} [{selected.slug}]. Public requests for every other hut are disabled.')
    return 0


if __name__=='__main__':raise SystemExit(main())
