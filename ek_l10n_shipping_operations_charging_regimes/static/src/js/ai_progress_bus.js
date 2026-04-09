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
        // Si estamos en una vista que muestra este registro, refrescarla
        // Nota: Odoo 17 no refresca automáticamente, forzamos un reload de la acción actual
        // si el ID coincide y es una vista de formulario/lista relevante.
        
        const controller = this.env.services.action.currentController;
        if (controller && controller.props.resModel === payload.model && controller.props.resId === payload.id) {
            // Solo recargar si el estado cambió a completado o error para habilitar botones,
            // o periódicamente para ver la barra de progreso.
            // Para la barra de progreso, lo ideal sería actualizar el estado local,
            // pero un reload() es lo más sencillo y robusto en V17 sin parchar OWL profundamente.
            
            console.log("AI Update received, reloading record:", payload.id);
            this.env.bus.trigger("RPC_NOTIFICATION", {
                type: "reload",
                model: payload.model,
                id: payload.id
            });
            
            // Forzar recarga de la vista actual
            if (controller.component && controller.component.model) {
                controller.component.model.load();
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
