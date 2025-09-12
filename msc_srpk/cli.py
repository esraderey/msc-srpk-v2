import argparse
import os
import sys
from .srpk_v2 import EnhancedSRPKManager
from .licensing import initialize_license, get_license_info, LicenseError, license_manager

def main():
    parser = argparse.ArgumentParser(prog="msc-srpk", description="MSC SRPK v2 - Code Knowledge Graph CLI")
    
    # Argumentos globales
    parser.add_argument("--license-key", help="Clave de licencia MSC SRPK")
    parser.add_argument("--no-license-check", action="store_true", help="Saltar verificación de licencia (solo desarrollo)")
    
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_an = sub.add_parser("analyze", help="Analyze a Python project")
    p_an.add_argument("path", help="Path to project")
    p_an.add_argument("--state", default="srpk_v2_state.json", help="State file path")

    p_te = sub.add_parser("test", help="Run tests (pytest/unittest/doctest/custom)")
    p_te.add_argument("--framework", default="pytest", choices=["pytest","unittest","doctest","custom"])

    p_rp = sub.add_parser("report", help="Generate quality report")
    p_rp.add_argument("--out", default="quality_report.json")

    p_fd = sub.add_parser("find", help="Find similar code")
    p_fd.add_argument("code", help="Code snippet")
    
    p_lic = sub.add_parser("license", help="License management")
    p_lic.add_argument("--info", action="store_true", help="Show license information")
    p_lic.add_argument("--validate", action="store_true", help="Validate current license")
    p_lic.add_argument("--refresh", action="store_true", help="Refresh license from server")

    args = parser.parse_args()
    
    # Verificar licencia si no se omite
    if not args.no_license_check:
        license_key = args.license_key or os.getenv('MSC_SRPK_LICENSE_KEY')
        
        if not license_key:
            print("❌ Error: Se requiere clave de licencia MSC SRPK")
            print("   Obtén tu licencia en: https://licenses.mscsrpk.com")
            print("   O usa: msc-srpk --license-key TU_LICENCIA")
            print("   O establece: export MSC_SRPK_LICENSE_KEY=TU_LICENCIA")
            sys.exit(1)
        
        try:
            if not initialize_license(license_key):
                print("❌ Error: Licencia inválida o expirada")
                print("   Verifica tu clave de licencia o contacta soporte")
                sys.exit(1)
            
            # Mostrar información de licencia
            license_info = get_license_info()
            if license_info:
                print(f"✅ Licencia válida: {license_info['license_type']} - {license_info['customer_name']}")
        except LicenseError as e:
            print(f"❌ Error de licencia: {e}")
            sys.exit(1)
    
    manager = EnhancedSRPKManager(getattr(args, "state", "srpk_v2_state.json"))

    if args.cmd == "analyze":
        if not os.path.exists(args.path):
            raise SystemExit(f"Error: Path '{args.path}' does not exist")
        print(f"Analyzing project: {args.path}")
        count = manager.analyze_project(args.path)
        print(f"✓ Analysis complete: {count} files processed")
        print(f"✓ State saved to: {manager.state_file}")

    elif args.cmd == "test":
        print(f"Running tests with {args.framework}...")
        results = manager.run_tests(args.framework)
        print(f"Total: {results['total_tests']}")
        print(f"Passed: {results['passed']}")
        print(f"Failed: {results['failed']}")
        print(f"Coverage: {results['coverage']:.1%}")

    elif args.cmd == "report":
        print(f"Generating quality report: {args.out}")
        ok = manager.generate_quality_report(args.out)
        if ok:
            print("✓ Report generated successfully")
            print(f"  JSON: {args.out}")
            print(f"  Markdown: {args.out.replace('.json','.md')}")
        else:
            print("✗ Failed to generate report")

    elif args.cmd == "find":
        res = manager.srpk.find_similar_code(args.code, threshold=0.7)
        if res:
            print(f"Found {len(res)} similar fragments:")
            for code_id, sim, node in res[:5]:
                print(f" - {code_id}: {sim:.2%}  :: {node.purpose}")
        else:
            print("No similar code found")
    
    elif args.cmd == "license":
        license_key = args.license_key or os.getenv('MSC_SRPK_LICENSE_KEY')
        
        if args.info:
            if not license_key:
                print("❌ No hay licencia configurada")
                sys.exit(1)
            
            if initialize_license(license_key):
                license_info = get_license_info()
                if license_info:
                    print("📋 Información de Licencia:")
                    print(f"   Tipo: {license_info['license_type']}")
                    print(f"   Cliente: {license_info['customer_name']}")
                    print(f"   Email: {license_info['email']}")
                    print(f"   Emitida: {license_info['issued_at']}")
                    if license_info.get('expires_at'):
                        print(f"   Expira: {license_info['expires_at']}")
                    print(f"   Entornos prod: {license_info['max_prod_environments']}")
                    print(f"   Entornos no-prod: {license_info['max_nonprod_environments']}")
                    print(f"   Características: {', '.join(license_info['features'])}")
            else:
                print("❌ Licencia inválida")
        
        elif args.validate:
            if not license_key:
                print("❌ No hay licencia configurada")
                sys.exit(1)
            
            print("🔍 Validando licencia...")
            if initialize_license(license_key):
                print("✅ Licencia válida")
            else:
                print("❌ Licencia inválida o expirada")
        
        elif args.refresh:
            if not license_key:
                print("❌ No hay licencia configurada")
                sys.exit(1)
            
            print("🔄 Refrescando licencia desde servidor...")
            if license_manager.refresh_license():
                print("✅ Licencia actualizada")
                license_info = get_license_info()
                if license_info:
                    print(f"   Cliente: {license_info['customer_name']}")
                    print(f"   Tipo: {license_info['license_type']}")
            else:
                print("❌ Error refrescando licencia")

if __name__ == "__main__":
    main()
