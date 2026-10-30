from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.main import require_platform_admin


@pytest.mark.asyncio
async def test_workspace_owner_does_not_inherit_platform_admin_permission():
    user = {"is_admin": False, "workspace_role": "owner", "user_id": "user-1"}

    with pytest.raises(HTTPException) as error:
        await require_platform_admin(user)

    assert error.value.status_code == 403
    assert "Platform Super Admin" in str(error.value.detail)


@pytest.mark.asyncio
async def test_workspace_admin_does_not_inherit_platform_admin_permission():
    user = {"is_admin": False, "workspace_role": "admin", "user_id": "user-2"}

    with pytest.raises(HTTPException) as error:
        await require_platform_admin(user)

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_explicit_platform_admin_flag_allows_global_read_only_console():
    user = {"is_admin": True, "workspace_role": "member", "user_id": "admin-1"}

    result = await require_platform_admin(user)

    assert result is user
