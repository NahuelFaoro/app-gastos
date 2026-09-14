from PySide6.QtCore import QThread, Signal, QTimer, QUrl, QCoreApplication
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QLineEdit,QMessageBox,QCheckBox
from .cloud_sync import CloudSync

class CloudJob(QThread):
    result=Signal(str,bool)
    def __init__(self,fn,parent=None):super().__init__(parent);self.fn=fn
    def run(self):
        try:self.result.emit(self.fn(),True)
        except Exception as e:self.result.emit(str(e),False)
        finally:self.fn=None

class CloudSyncPanel(QFrame):
    data_changed=Signal()
    def __init__(self,db,parent=None):
        super().__init__(parent);self.db=db;self.service=CloudSync(db);self.job=None;self.setObjectName('Card')
        box=QVBoxLayout(self);box.setContentsMargins(22,20,22,20)
        title=QLabel('Cuenta privada · PC y teléfonos');title.setObjectName('SectionTitle');box.addWidget(title)
        hint=QLabel('Usá la misma cuenta en todos tus dispositivos. Primero se guarda localmente; al conectarse se intercambian los cambios.');hint.setWordWrap(True);hint.setObjectName('Muted');box.addWidget(hint)
        self.email=QLineEdit();self.email.setPlaceholderText('Email de tu cuenta de App Gastos');box.addWidget(self.email)
        self.password=QLineEdit();self.password.setPlaceholderText('Contraseña');self.password.setEchoMode(QLineEdit.EchoMode.Password);box.addWidget(self.password)
        self.show_password=QCheckBox('Mostrar contraseña');self.show_password.toggled.connect(lambda visible:self.password.setEchoMode(QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password));box.addWidget(self.show_password)
        self.password.returnPressed.connect(self.login)
        self.status=QLabel('Sin sesión');self.status.setWordWrap(True);box.addWidget(self.status)
        self.buttons=[]
        for text,fn in [('Iniciar sesión',self.login),('Crear o confirmar cuenta en la app',lambda:QDesktopServices.openUrl(QUrl('https://app-gastos-movil.pages.dev/'))),('Activar sincronización',self.enable),('Sincronizar ahora',lambda:self.run(lambda:self.service.sync())),('Pausar',self.pause),('Cerrar sesión',lambda:self.run(self.service.logout))]:
            b=QPushButton(text);b.clicked.connect(fn);self.buttons.append(b);box.addWidget(b)
        help=QLabel('Si hay cambios simultáneos, no se sobrescriben automáticamente. Las opciones siguientes guardan un respaldo antes de reemplazar una copia completa.');help.setWordWrap(True);help.setObjectName('SmallMuted');box.addWidget(help)
        for text,choice in [('Conservar Desktop en la nube','local'),('Recibir copia de la nube','remote')]:
            b=QPushButton(text);b.setObjectName('SecondaryButton');b.clicked.connect(lambda checked=False,v=choice:self.resolve(v));self.buttons.append(b);box.addWidget(b)
        self.timer=QTimer(self);self.timer.setInterval(60000);self.timer.timeout.connect(self.automatic);self.timer.start()
        QTimer.singleShot(500,self.restore)
        QCoreApplication.instance().aboutToQuit.connect(self.shutdown)

    def restore(self):
        try:
            s=self.service.restore()
            if s:self.email.setText(s['user']['email']);self.status.setText('Sesión guardada · '+s['user']['email']);self.automatic()
        except Exception:self.status.setText('Iniciá sesión para usar la sincronización.')

    def run(self,fn):
        if self.job is not None:return
        for b in self.buttons:b.setEnabled(False)
        self.status.setText('Conectando…');self.job=CloudJob(fn,self);self.job.result.connect(self.done);self.job.finished.connect(self.finished);self.job.start()

    def done(self,message,success):
        self.status.setText(message)
        if success:self.data_changed.emit()

    def finished(self):
        self.job.deleteLater();self.job=None
        for b in self.buttons:b.setEnabled(True)

    def login(self):
        if self.job is not None:return
        email,password=self.email.text().strip(),self.password.text();self.password.clear()
        self.show_password.setChecked(False)
        self.run(lambda:self.service.login(email,password))

    def enable(self):
        if QMessageBox.question(self,'Activar sincronización','Esto enviará una copia de tus registros a tu espacio privado en Supabase. Se guardará un respaldo local primero. ¿Continuar?')==QMessageBox.StandardButton.Yes:self.run(lambda:self.service.sync(enable=True))

    def pause(self):self.db.set_setting('cloud_enabled','0');self.status.setText('Sincronización pausada.')

    def automatic(self):
        if self.service.session and self.db.get_setting('cloud_enabled','0')=='1':self.run(lambda:self.service.sync())

    def resolve(self,choice):
        message='Esto reemplaza la copia de la nube por Desktop.' if choice=='local' else 'Esto reemplaza los registros compatibles de Desktop por la nube.'
        if QMessageBox.question(self,'Resolver copias',message+' Se guardará un respaldo local. ¿Continuar?')==QMessageBox.StandardButton.Yes:self.run(lambda:self.service.resolve(choice))

    def shutdown(self):
        self.timer.stop()
        if self.job is not None:self.job.wait()
