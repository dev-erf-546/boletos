"""
Agrega boletos a una rifa existente por rango de números.
Solo crea números que aún no existen para esa rifa.

Uso en producción:
    python manage.py shell
    >>> exec(open('scripts/agregar_boletos.py', encoding='utf-8').read())
"""
from django.db import transaction

from eventos.models import Boleto, Rifa


def _leer_entero(mensaje, minimo=1):
    while True:
        raw = input(mensaje).strip()
        try:
            valor = int(raw)
        except ValueError:
            print("  Ingresa un número entero válido.")
            continue
        if valor < minimo:
            print(f"  El valor debe ser >= {minimo}.")
            continue
        return valor


def agregar_boletos():
    print("\n=== Agregar boletos a una rifa ===\n")

    rifas = list(Rifa.objects.order_by("-fecha_creacion").values("id", "nombre", "boletos_total"))
    if not rifas:
        print("No hay rifas registradas.")
        return

    print("Rifas disponibles:")
    for r in rifas:
        print(f"  [{r['id']}] {r['nombre']} — total actual: {r['boletos_total']}")

    rifa_id = _leer_entero("\nID de la rifa: ", minimo=1)
    try:
        rifa = Rifa.objects.get(pk=rifa_id)
    except Rifa.DoesNotExist:
        print(f"Rifa con ID {rifa_id} no encontrada.")
        return

    print(f"\nRifa seleccionada: {rifa.nombre} (total registrado: {rifa.boletos_total})")

    numero_inicio = _leer_entero("Número inicial del rango: ", minimo=1)
    numero_fin = _leer_entero("Número final del rango: ", minimo=1)

    if numero_inicio > numero_fin:
        numero_inicio, numero_fin = numero_fin, numero_inicio
        print(f"  Rango ajustado: {numero_inicio} - {numero_fin}")

    cantidad_rango = numero_fin - numero_inicio + 1
    existentes = set(
        Boleto.objects.filter(
            rifa=rifa,
            numero__gte=numero_inicio,
            numero__lte=numero_fin,
        ).values_list("numero", flat=True)
    )
    numeros_nuevos = [n for n in range(numero_inicio, numero_fin + 1) if n not in existentes]
    omitidos = cantidad_rango - len(numeros_nuevos)

    print(f"\nResumen del rango {numero_inicio} - {numero_fin}:")
    print(f"  A crear (nuevos): {len(numeros_nuevos)}")
    print(f"  Ya existentes (se omitirán): {omitidos}")

    if not numeros_nuevos:
        print("\nNo hay números nuevos que crear. Operación cancelada.")
        return

    actualizar_total = False
    if numero_fin > rifa.boletos_total:
        print(
            f"\nEl total de la rifa pasaría de {rifa.boletos_total} "
            f"a {numero_fin} (boletos_total)."
        )
        resp = input("¿Actualizar boletos_total de la rifa? [s/N]: ").strip().lower()
        actualizar_total = resp in ("s", "si", "sí", "y", "yes")

    confirmar = input(f"\n¿Crear {len(numeros_nuevos)} boleto(s)? [s/N]: ").strip().lower()
    if confirmar not in ("s", "si", "sí", "y", "yes"):
        print("Operación cancelada.")
        return

    creados = 0
    with transaction.atomic():
        for numero in numeros_nuevos:
            _, created = Boleto.objects.get_or_create(
                rifa=rifa,
                numero=numero,
                defaults={"estado": "D"},
            )
            if created:
                creados += 1

        if actualizar_total and numero_fin > rifa.boletos_total:
            rifa.boletos_total = numero_fin
            rifa.save(update_fields=["boletos_total"])

    print(f"\nListo: {creados} boleto(s) creados, {omitidos} omitido(s) (ya existían).")
    if actualizar_total:
        print(f"boletos_total actualizado a {rifa.boletos_total}.")
    else:
        rifa.refresh_from_db()
        print(f"boletos_total sin cambios: {rifa.boletos_total}.")


agregar_boletos()
