from django.urls import path
from . import views

urlpatterns = [
    path('', views.menu_principal, name='menu_principal'), # URL: /reservas/
    path('ingreso/', views.ingreso, name='ingreso'), # URL: /reservas/ingreso/
    path('ingreso/ticket/<int:reserva_id>/', views.ticket_ingreso_pdf, name='ticket_ingreso_pdf'),
    path('mensualidad/ticket/<int:reserva_id>/', views.ticket_mensualidad_pdf, name='ticket_mensualidad_pdf'),
    path('salida/', views.salida, name='salida'), # URL: /reservas/salida/
    path('dashboard/', views.dashboard_admin, name='dashboard_admin'), # URL: /reservas/dashboard/  
    
    # RUTA PARA ELIMINAR REGISTRO (SE USARA PRONTO)
    path('eliminar/<int:reserva_id>/', views.eliminar_reserva, name='eliminar_reserva'), # URL: /reservas/eliminar/1/   

    # RUTA PARA GENERAR REPORTE DIARIO EN PDF
    path('reporte-diario/', views.reporte_diario_pdf, name='reporte_diario'), # URL: /reservas/reporte-diario/
    path('generar-pdf-salida/<int:reserva_id>/', views.generar_pdf_salida, name='generar_pdf_salida'), # URL: /reservas/generar-pdf-salida/1/
    path('reporte-placa/', views.generar_reporte_placa_pdf, name='reporte_placa'), # URL: /reservas/reporte-placa/?placa=ABC123
    path('mensualidad/control/', views.control_mensualidad, name='control_mensualidad'), # URL: /reservas/mensualidad/control/
    path('reporte-pdf/', views.reporte_diario_pdf, name='reporte_diario_pdf'), # URL: /reservas/reporte-pdf/

]