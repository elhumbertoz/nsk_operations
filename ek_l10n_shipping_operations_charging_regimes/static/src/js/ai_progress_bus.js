/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart } from "@odoo/owl";

// Escuchador del Bus para actualizaciones de IA
// Este componente se instancia globalmente para escuchar cambios de estado de la IA
export class AIProgressBusListener {
    constructor(env) {
        this.env = env;
        this.bus = env.services.bus_service;
        this.action = env.services.action;
        
        // Suscribirse al canal de notificaciones
        this.bus.addChannel("ai_extraction_update");
        this.bus.addEventListener("notification", this.onNotification.bind(this));
    }

    onNotification({ detail: notifications }) {
        for (const notif of notifications) {
            if (notif.type === "ai_extraction_update") {
                const payload = notif.payload;
                this.handleUpdate(payload);
            }
        }
    }

    handleUpdate(payload) {
        const actionService = this.env.services.action;
        let controller = actionService.currentController;
        
        if (!controller) {
            console.log("No active controller found for AI update");
            return;
        }

        console.log("Processing AI update for", payload.model, payload.id, "Current Controller:", controller.props.resModel);

        // Notify background records (standard Odoo reload signal)
        this.env.bus.trigger("RPC_NOTIFICATION", {
            type: "reload",
            model: payload.model,
            id: payload.id
        });

        // Identify if the controller is our wizard or the main record
        const isMainRecord = controller.props.resModel === payload.model && controller.props.resId === payload.id;
        let isProgressWizard = false;

        if (controller.props.resModel === 'ek.ai.extraction.progress.wizard') {
            // In a wizard, we check its internal data to match the source record
            const data = controller.component?.model?.root?.data;
            if (data && data.res_model === payload.model && data.res_id === payload.id) {
                isProgressWizard = true;
            }
        }

        if (isMainRecord || isProgressWizard) {
            console.log("AI Target matched. Reloading component...");
            
            if (controller.component && controller.component.model) {
                controller.component.model.load().then(() => {
                    console.log("Component reloaded successfully");
                    
                    // Auto-close logic
                    if (isProgressWizard && payload.status === 'completed') {
                        console.log("Extraction COMPLETED. Closing modal in 1.5s...");
                        setTimeout(() => {
                            // Verify we are still in the wizard before closing
                            const current = actionService.currentController;
                            if (current && current.props.resModel === 'ek.ai.extraction.progress.wizard') {
                                actionService.restore();
                            }
                        }, 1500);
                    }
                });
            }
        }
    }
}

// Registro del servicio/inicializador
import { registry } from "@web/core/registry";

const aiProgressService = {
    dependencies: ["bus_service", "action"],
    start(env) {
        return new AIProgressBusListener(env);
    },
};

registry.category("services").add("ai_progress_bus", aiProgressService);
