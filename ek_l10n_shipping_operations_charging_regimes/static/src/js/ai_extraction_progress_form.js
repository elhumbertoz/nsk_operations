/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { onMounted, onWillUnmount } from "@odoo/owl";

/**
 * FormController personalizado para el wizard de progreso de extracción IA.
 *
 * DISEÑO:
 * - El wizard se abre con un res_id real (creado en Python antes de retornar la acción).
 * - Esto garantiza que this.model.load() use webRead() —lectura real al servidor—
 *   en lugar de onchange(), que no refleja los cambios del hilo asíncrono.
 * - El polling lee los campos computados del wizard (status, progress, message)
 *   que a su vez leen el registro fuente actualizado por el hilo.
 * - Al llegar a "completed", this.discard() cierra el dialog limpiamente
 *   (el record no está dirty porque todos los campos son readonly/computados).
 */
class AIExtractionProgressController extends FormController {
    setup() {
        super.setup();
        this._pollingInterval = null;
        this._isLoading = false;

        onMounted(() => {
            console.log("[AIExtraction] Modal abierto, iniciando polling...", {
                resId: this.model.root.resId,
                resModel: this.model.root.resModel,
            });
            this._startPolling();
        });

        onWillUnmount(() => {
            this._stopPolling();
        });
    }

    _startPolling() {
        this._pollingInterval = setInterval(async () => {
            if (this._isLoading) return;
            this._isLoading = true;
            try {
                await this.model.load();
                const data = this.model.root.data;
                const status = data.status;
                const progress = data.progress;
                console.log(`[AIExtraction] Poll: status=${status}, progress=${progress}`);

                if (status === "completed") {
                    this._stopPolling();
                    console.log("[AIExtraction] Completado. Cerrando modal en 1.5s...");
                    setTimeout(() => this.discard(), 1500);
                } else if (status === "error") {
                    this._stopPolling();
                    console.log("[AIExtraction] Error detectado. Polling detenido.");
                }
            } catch (e) {
                console.error("[AIExtraction] Error en polling:", e);
                this._stopPolling();
            } finally {
                this._isLoading = false;
            }
        }, 2000);
    }

    _stopPolling() {
        if (this._pollingInterval) {
            clearInterval(this._pollingInterval);
            this._pollingInterval = null;
        }
    }
}

const AIExtractionProgressView = {
    ...formView,
    Controller: AIExtractionProgressController,
};

registry.category("views").add("ek_ai_extraction_progress", AIExtractionProgressView);
