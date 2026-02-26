# Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
GitHub OAuth Authenticator

Custom GitHub OAuth authenticator with team integration support.
"""

from __future__ import annotations

from oauthenticator.github import GitHubOAuthenticator
from oauthenticator.oauth2 import OAuthCallbackHandler


class _GitHubAppInstallCallbackHandler(OAuthCallbackHandler):
    """Callback handler that gracefully handles GitHub App installation redirects.

    When a user installs a GitHub App, GitHub redirects to the OAuth callback URL
    with ``setup_action=install`` but without the ``state`` parameter that the
    standard OAuth flow requires.  Instead of returning a 400 error, detect this
    case and redirect the user back to the spawn page.
    """

    async def get(self):
        if self.get_argument("setup_action", "") == "install" and not self.get_argument("state", ""):
            self.redirect(self.hub.base_url + "spawn")
            return
        await super().get()


class CustomGitHubOAuthenticator(GitHubOAuthenticator):
    """GitHub OAuth authenticator with access token preservation."""

    name = "github"
    callback_handler = _GitHubAppInstallCallbackHandler

    async def authenticate(self, handler, data=None):
        result = await super().authenticate(handler, data)
        if not result:
            return None

        access_token = result["auth_state"]["access_token"]
        result["auth_state"]["access_token"] = access_token

        return result
