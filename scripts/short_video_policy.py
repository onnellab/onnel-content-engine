"""Deterministic fail-closed policy for unattended English YouTube Shorts."""
from __future__ import annotations

import re
from pathlib import Path

from short_video_pipeline import ROOT, VideoError, digest, load_json
from short_video_recorder import RecordingError, managed_recording_attestation

DEFAULT_POLICY = ROOT / 'data/video_publish_policy.json'
_REQUIRED = {
    'schema_version',
    'mode',
    'destination',
    'locale',
    'privacy',
    'publish_mode',
    'made_for_kids',
    'synthetic_media',
    'allow_narration',
    'require_released_app',
    'require_real_recording',
    'require_managed_recording',
    'forbidden_marketing_terms',
}
_CJK = re.compile(r'[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]')
_TEST_ASSET = re.compile(r'(^|[/_.-])(test|fixture|synthetic|colorbars?|sample)([/_.-]|$)', re.I)


class PolicyError(VideoError):
    pass
def validate_policy(policy: dict) -> dict:
    if not isinstance(policy, dict) or set(policy) != _REQUIRED:
        raise PolicyError('automatic_policy_fields_invalid')
    if policy['schema_version'] != 1 or policy['mode'] != 'automatic_fail_closed':
        raise PolicyError('automatic_policy_version_invalid')
    if policy['destination'] != 'youtube_shorts' or policy['locale'] != 'en':
        raise PolicyError('automatic_policy_scope_invalid')
    if policy['privacy'] not in {'private', 'unlisted', 'public'}:
        raise PolicyError('automatic_policy_privacy_invalid')
    if policy['publish_mode'] != 'on_worker_due':
        raise PolicyError('automatic_policy_publish_mode_invalid')
    for key in ('made_for_kids', 'synthetic_media', 'allow_narration',
                'require_released_app', 'require_real_recording',
                'require_managed_recording'):
        if type(policy[key]) is not bool:
            raise PolicyError('automatic_policy_boolean_invalid')
    terms = policy['forbidden_marketing_terms']
    if (not isinstance(terms, list) or len(terms) > 64
            or any(not isinstance(term, str) or not term.strip() or len(term) > 64 for term in terms)):
        raise PolicyError('automatic_policy_terms_invalid')
    return policy


def load_policy(path: Path = DEFAULT_POLICY) -> dict:
    return validate_policy(load_json(path))


def policy_digest(policy: dict) -> str:
    return digest(validate_policy(policy))


def _copy(job: dict) -> str:
    brief = job['brief']
    parts = [brief['hook'], brief['title'], brief['description'], brief['cta']]
    parts.extend(item['text'] for item in brief['captions'])
    return '\n'.join(parts)
def automatic_choices(job: dict, policy: dict, *, asset_root=None) -> dict:
    """Return upload choices only when unattended publication is objectively safe."""
    policy = validate_policy(policy)
    if job['brief'].get('locale') != policy['locale']:
        raise PolicyError('automatic_review_locale')
    if job['brief'].get('test_only') or not job.get('upload_eligible'):
        raise PolicyError('automatic_review_test_or_ineligible')
    if policy['require_released_app'] and not job.get('product'):
        raise PolicyError('automatic_review_product_snapshot')
    if not policy['allow_narration'] and 'narration' in job['brief']:
        raise PolicyError('automatic_review_narration_not_allowed')
    recording = job['brief'].get('recording', '')
    if policy['require_real_recording'] and _TEST_ASSET.search(recording):
        raise PolicyError('automatic_review_test_recording_name')
    copy = _copy(job)
    if _CJK.search(copy):
        raise PolicyError('automatic_review_non_english_copy')
    folded = copy.casefold()
    for term in policy['forbidden_marketing_terms']:
        if term.casefold() in folded:
            raise PolicyError('automatic_review_forbidden_marketing_claim')
    if copy.count('!') > 1:
        raise PolicyError('automatic_review_excessive_exclamation')
    if policy['require_managed_recording']:
        if asset_root is None:
            raise PolicyError('automatic_review_managed_recording_required')
        try:
            managed_recording_attestation(asset_root, job)
        except RecordingError as exc:
            raise PolicyError(str(exc)) from exc
    return {
        'made_for_kids': policy['made_for_kids'],
        'synthetic_media': policy['synthetic_media'],
        'privacy': policy['privacy'],
        'publish_at': None,
        'publish_approved': policy['privacy'] != 'private',
    }


def policy_summary(policy: dict) -> dict:
    policy = validate_policy(policy)
    return {
        'mode': policy['mode'],
        'destination': policy['destination'],
        'locale': policy['locale'],
        'privacy': policy['privacy'],
        'publish_mode': policy['publish_mode'],
        'human_review_required': False,
        'fail_closed': True,
        'managed_recording_required': policy['require_managed_recording'],
        'policy_hash': policy_digest(policy),
    }
