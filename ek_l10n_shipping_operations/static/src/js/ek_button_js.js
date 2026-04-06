/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { useService } from "@web/core/utils/hooks";
import { Component, xml } from "@odoo/owl";

export class ButtonJSListController extends ListController {
  setup() {
    super.setup();
    this.action = useService("action");
  }

  async onClickOpenWizard() {
    var context = {
      active_model: this.modelName,

    };
    this.action.doAction({
      res_model: 'ek.generate.shipping.trade.numbers.wizard',
      views: [[this.view_ek_generate_shipping_trade_numbers_form, 'form']],
      target: 'new',
      type: 'ir.actions.act_window',
      name: 'Trade Number',
      context: context,

    });
  }
}

// Cliente action para refrescar la vista del formulario (similar a nsk_pdf_manager)
const refreshDeliveryFieldsAction = async (env, action) => {
  const { message, parent_model, parent_id } = action.params || {};

  // Mostrar notificación de éxito
  if (message) {
    env.services.notification.add(message, {
      type: 'success',
      sticky: false,
    });
  }

  // Refrescar la vista actual recargando el formulario
  try {
    const actionService = env.services.action;

    // Cerrar el diálogo/wizard actual si existe
    if (actionService) {
      const currentController = actionService.currentController;
      if (currentController && currentController.props && currentController.props.close) {
        currentController.props.close();
      }
    }

    // Si tenemos parent_model y parent_id, recargar la vista del formulario
    if (parent_model && parent_id && actionService) {
      // Recargar la vista del formulario del documento específico
      await actionService.doAction({
        type: 'ir.actions.act_window',
        res_model: parent_model,
        res_id: parent_id,
        views: [[false, 'form']],
        view_mode: 'form',
        target: 'current',
      });
    }
  } catch (error) {
    console.error('DEBUG_DEVELOPMENT: Error al refrescar vista:', error);
  }
};

registry.category("actions").add("refresh_delivery_fields", refreshDeliveryFieldsAction);
registry.category("views").add("ek_button_js_tree", {
  ...listView,
  Controller: ButtonJSListController,
  buttonTemplate: "ek_l10n_shipping_operations.ButtonJSListView.Buttons",
});

// Exponer la función para debugging (solo en desarrollo)
if (typeof window !== 'undefined') {
  window.debugDeliveryFields = {
    // Verificar si el módulo se cargó
    checkModuleLoaded: () => {
      console.log('✓ Módulo ek_button_js.js cargado correctamente');
      return true;
    },

    // Verificar si la acción está registrada
    checkActionRegistered: () => {
      try {
        // Intentar acceder al registry a través del loader de Odoo
        const loader = odoo.loader;
        if (loader && loader.modules) {
          const module = loader.modules.get('ek_l10n_shipping_operations.ek_button_js');
          console.log('Módulo encontrado:', !!module);
        }
        console.log('Para verificar la acción registrada, ejecuta en la consola:');
        console.log('  odoo.loader.modules.get("@web/core/registry").category("actions").get("refresh_delivery_fields")');
        return true;
      } catch (e) {
        console.error('Error verificando acción:', e);
        return false;
      }
    }
  };

  console.log('DEBUG_DEVELOPMENT: Scripts de debugging disponibles.');
  console.log('Ejecuta en la consola: window.debugDeliveryFields.checkModuleLoaded()');
  console.log('Para verificar la acción: window.debugDeliveryFields.checkActionRegistered()');
}
