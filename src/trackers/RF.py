# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import glob
import os
import re
from typing import Any, Optional

from src.console import console
from src.get_desc import DescriptionBuilder
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D
from src.uploadscreens import UploadScreensManager

Meta = dict[str, Any]
Config = dict[str, Any]


class RF(UNIT3D):
    def __init__(self, config: Config) -> None:
        super().__init__(config, tracker_name='RF')
        self.config: Config = config
        self.common = COMMON(config)
        self.tracker = 'RF'
        self.base_url = 'https://reelflix.cc'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.requests_url = f'{self.base_url}/api/requests/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []
        self.disallowed_img_hosts = ['lostimg']
        # Don't run check_image_hosts in the global pre-upload phase;
        # images are uploaded to reelflix lazily from get_description instead.
        self.deferred_image_host_check = True

    async def check_image_hosts(self, meta: dict[str, Any]) -> None:
        """Upload screenshots to img.reelflix.cc, independently of the global image host."""
        if meta.get('skip_imghost_upload', False):
            return

        new_images_key = 'RF_images_key'
        if new_images_key not in meta:
            meta[new_images_key] = []

        # Gather local PNG screenshots from the tmp folder
        screenshots_dir = os.path.join(meta['base_dir'], 'tmp', meta['uuid'])
        skip_prefixes = ('FILE', 'PLAYLIST', 'POSTER')
        png_files = sorted(
            f for f in await asyncio.to_thread(glob.glob, os.path.join(screenshots_dir, '*.png'))
            if not os.path.basename(f).startswith(skip_prefixes)
        )

        if not png_files:
            console.print("[yellow]RF: No local screenshots found; using global image list.[/yellow]")
            meta[new_images_key] = meta.get('image_list', [])
            return

        screens = int(meta.get('screens') or len(png_files))
        original_imghost = meta.get('imghost')
        meta['imghost'] = 'reelflix'

        uploadscreens_manager = UploadScreensManager(self.config)
        uploaded_images, _ = await uploadscreens_manager.upload_screens(
            meta,
            screens,
            1,
            0,
            screens,
            png_files[:screens],
            {new_images_key: meta[new_images_key]},
        )

        if uploaded_images:
            meta[new_images_key] = uploaded_images
            console.print(f"[green]RF: Uploaded {len(uploaded_images)} image(s) to img.reelflix.cc[/green]")
        else:
            console.print("[yellow]RF: Reelflix image upload failed; falling back to global image list.[/yellow]")
            meta[new_images_key] = meta.get('image_list', [])

        meta['imghost'] = original_imghost

    async def get_description(self, meta: dict[str, Any]) -> dict[str, str]:
        # Upload to reelflix here rather than in the global pre-upload phase,
        # so images are only sent to img.reelflix.cc when RF actually uploads.
        if not meta.get('RF_images_key'):
            await self.check_image_hosts(meta)
        rf_images = meta.get('RF_images_key') or meta.get('image_list')
        return {
            "description": await DescriptionBuilder(self.tracker, self.config).unit3d_edit_desc(
                meta, comparison=True, image_list=rf_images
            )
        }

    async def get_additional_checks(self, meta: Meta) -> bool:
        should_continue = True

        genres = f"{meta.get('keywords', '')} {meta.get('combined_genres', '')}"
        adult_keywords = ['xxx', 'erotic', 'porn', 'adult', 'orgy']
        if any(re.search(rf'(^|,\s*){re.escape(keyword)}(\s*,|$)', genres, re.IGNORECASE) for keyword in adult_keywords):
            if not meta['unattended']:
                console.print('[bold red]Erotic not allowed at RF.')
            should_continue = False
        if meta.get('category') == "TV":
            if not meta['unattended']:
                console.print('[bold red]RF only ALLOWS Movies.')
            should_continue = False

        return should_continue

    async def get_name(self, meta: Meta) -> dict[str, str]:
        rf_name = str(meta.get('name', ''))
        tag_value = str(meta.get('tag', ''))
        tag_lower = tag_value.lower()
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]

        if tag_value == "" or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                rf_name = re.sub(f"-{invalid_tag}", "", rf_name, flags=re.IGNORECASE)
            rf_name = f"{rf_name}-NoGroup"

        return {'name': rf_name}

    async def get_type_id(
        self,
        meta: Meta,
        type: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False
    ) -> dict[str, str]:
        type_id = {
            'DISC': '43',
            'REMUX': '40',
            'WEBDL': '42',
            'WEBRIP': '45',
            # 'FANRES': '6',
            'ENCODE': '41',
            'HDTV': '35',
        }
        if mapping_only:
            return type_id
        elif reverse:
            return {v: k for k, v in type_id.items()}
        type_value = str(type) if type is not None else str(meta.get('type', ''))
        return {'type_id': type_id.get(type_value, '0')}

    async def get_resolution_id(
        self,
        meta: Meta,
        resolution: Optional[str] = None,
        reverse: bool = False,
        mapping_only: bool = False
    ) -> dict[str, str]:
        resolution_id = {
            # '8640p':'10',
            '4320p': '1',
            '2160p': '2',
            # '1440p' : '3',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '480p': '8',
            '480i': '9'
        }
        if mapping_only:
            return resolution_id
        elif reverse:
            return {v: k for k, v in resolution_id.items()}
        resolution_value = str(resolution) if resolution is not None else str(meta.get('resolution', ''))
        return {'resolution_id': resolution_id.get(resolution_value, '10')}
