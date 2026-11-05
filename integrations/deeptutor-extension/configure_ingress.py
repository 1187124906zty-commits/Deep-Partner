from pathlib import Path
import subprocess

site='''tutor.example.invalid {
    encode gzip
    @remembered_browser {
        path /login
        header_regexp trusted_cookie Cookie (^|;\\s*)__Host-dt_trusted=[^;]+
        not query password=1
    }
    handle @remembered_browser {
        rewrite * /access/quick-login
        reverse_proxy 127.0.0.1:8008
    }
    handle /register {
        redir /access/request 303
    }
    handle /access {
        redir /access/request 303
    }
    handle /api/coder/* {
        reverse_proxy 127.0.0.1:8010
    }
    handle /access/* {
        reverse_proxy 127.0.0.1:8008
    }
    handle {
        reverse_proxy 127.0.0.1:3783 {
            flush_interval -1
        }
    }
}
'''
path=Path('/srv/deeptutor/ingress.caddy')
path.write_text(site)
subprocess.run(['sudo','-n','install','-m','644',str(path),'/etc/caddy/deeptutor.caddy'],check=True)
subprocess.run(['sudo','-n','caddy','validate','--config','/etc/caddy/Caddyfile','--adapter','caddyfile'],check=True)
subprocess.run(['sudo','-n','systemctl','reload','caddy'],check=True)
print('Code artifact routes configured; native Tutor remains the only chat interface.')
