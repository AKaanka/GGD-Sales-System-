/** @odoo-module **/

/**
 * A "Fetch mail" button in the chatter topbar, beside Send message (#49).
 *
 * Incoming mail is polled, not pushed: the Fetchmail cron runs every five
 * minutes, so a reply can sit unseen for that long. Odoo's own Fetch Now lives
 * in Settings > Technical > Incoming Mail Servers, which is three navigations
 * away and needs Settings rights that CRM users must not have (#7).
 *
 * The button only appears on crm.lead. The rate limit is enforced on the
 * server, not by disabling this button: a disabled button is a suggestion,
 * and the thing being protected is a shared IMAP endpoint that will lock the
 * whole mailbox out if it is hammered.
 */

import { Chatter } from "@mail/chatter/web_portal/chatter";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";

patch(Chatter.prototype, {
    setup() {
        super.setup(...arguments);
        this.ggdOrm = useService("orm");
        this.ggdNotification = useService("notification");
        this.ggdFetch = useState({ busy: false });
    },

    get ggdCanFetchMail() {
        return this.props.threadModel === "crm.lead";
    },

    async ggdFetchIncomingMail() {
        if (this.ggdFetch.busy) {
            return;
        }
        this.ggdFetch.busy = true;
        try {
            const result = await this.ggdOrm.call(
                "crm.lead",
                "ggd_fetch_incoming_mail",
                []
            );
            let type = "warning";
            if (result.ok) {
                type = result.count ? "success" : "info";
            }
            this.ggdNotification.add(result.message, { type });
            if (result.ok && result.count && this.state.thread) {
                // Pull what just arrived into the open chatter. Without this
                // the button reports success and the screen does not change,
                // which reads as a broken button.
                await this.state.thread.fetchNewMessages();
            }
        } finally {
            this.ggdFetch.busy = false;
        }
    },
});
