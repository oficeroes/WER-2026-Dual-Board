/* JNIPROBE.c —— 用 JNI 从 App 进程里直接向 Android 要摄像头句柄
 *
 * 链路：
 *   JNI_GetCreatedJavaVMs -> JavaVM
 *   AttachCurrentThread   -> JNIEnv
 *   ActivityThread.currentApplication() -> Application(Context)
 *   getSystemService("usb") -> UsbManager
 *   getDeviceList().values().toArray() -> UsbDevice[]
 *   找到 090c:037c -> hasPermission() -> openDevice() -> getFileDescriptor() -> dup()
 *
 * 所有 JNI 调用都在 fork 出的子进程里执行，每一步的结果用固定结构写回管道，
 * 父进程（=服务器）读最后一份结果并报给电脑。子进程崩了也不影响服务。
 *
 * 服务器 0.0.0.0:9001
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <stdint.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <dlfcn.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/select.h>

extern void Printf(const char *format, ...);

/* ---------------- 最小 jni 定义（顺序与 jni.h 一致） ---------------- */
typedef int32_t  jint;
typedef int64_t  jlong;
typedef signed char jbyte;
typedef unsigned char jboolean;
typedef unsigned short jchar;
typedef short jshort;
typedef float jfloat;
typedef double jdouble;
typedef jint jsize;

struct _jobject;
typedef struct _jobject *jobject;
typedef jobject jclass;
typedef jobject jstring;
typedef jobject jarray;
typedef jobject jobjectArray;
typedef union jvalue {
    jboolean z; jbyte b; jchar c; jshort s; jint i; jlong j;
    jfloat f; jdouble d; jobject l;
} jvalue;
struct _jmethodID;
typedef struct _jmethodID *jmethodID;
struct _jfieldID;
typedef struct _jfieldID *jfieldID;

struct JNINativeInterface_;
typedef const struct JNINativeInterface_ *JNIEnv;

struct JNINativeInterface_ {
    void *reserved0, *reserved1, *reserved2, *reserved3;
    jint    (*GetVersion)(JNIEnv *);
    jclass  (*DefineClass)(JNIEnv *, const char *, jobject, const jbyte *, jsize);
    jclass  (*FindClass)(JNIEnv *, const char *);
    jmethodID (*FromReflectedMethod)(JNIEnv *, jobject);
    void *  (*FromReflectedField)(JNIEnv *, jobject);
    jobject (*ToReflectedMethod)(JNIEnv *, jclass, jmethodID, jboolean);
    jclass  (*GetSuperclass)(JNIEnv *, jclass);
    jboolean(*IsAssignableFrom)(JNIEnv *, jclass, jclass);
    jobject (*ToReflectedField)(JNIEnv *, jclass, void *, jboolean);
    jint    (*Throw)(JNIEnv *, jobject);
    jint    (*ThrowNew)(JNIEnv *, jclass, const char *);
    jobject (*ExceptionOccurred)(JNIEnv *);
    void    (*ExceptionDescribe)(JNIEnv *);
    void    (*ExceptionClear)(JNIEnv *);
    void    (*FatalError)(JNIEnv *, const char *);
    jint    (*PushLocalFrame)(JNIEnv *, jint);
    jobject (*PopLocalFrame)(JNIEnv *, jobject);
    jobject (*NewGlobalRef)(JNIEnv *, jobject);
    void    (*DeleteGlobalRef)(JNIEnv *, jobject);
    void    (*DeleteLocalRef)(JNIEnv *, jobject);
    jboolean(*IsSameObject)(JNIEnv *, jobject, jobject);
    jobject (*NewLocalRef)(JNIEnv *, jobject);
    jint    (*EnsureLocalCapacity)(JNIEnv *, jint);
    jobject (*AllocObject)(JNIEnv *, jclass);
    jobject (*NewObject)(JNIEnv *, jclass, jmethodID, ...);
    jobject (*NewObjectV)(JNIEnv *, jclass, jmethodID, va_list);
    jobject (*NewObjectA)(JNIEnv *, jclass, jmethodID, const jvalue *);
    jclass  (*GetObjectClass)(JNIEnv *, jobject);
    jboolean(*IsInstanceOf)(JNIEnv *, jobject, jclass);
    jmethodID (*GetMethodID)(JNIEnv *, jclass, const char *, const char *);
    jobject (*CallObjectMethod)(JNIEnv *, jobject, jmethodID, ...);
    jobject (*CallObjectMethodV)(JNIEnv *, jobject, jmethodID, va_list);
    jobject (*CallObjectMethodA)(JNIEnv *, jobject, jmethodID, const jvalue *);
    jboolean(*CallBooleanMethod)(JNIEnv *, jobject, jmethodID, ...);
    jboolean(*CallBooleanMethodV)(JNIEnv *, jobject, jmethodID, va_list);
    jboolean(*CallBooleanMethodA)(JNIEnv *, jobject, jmethodID, const jvalue *);
    jbyte   (*CallByteMethod)(JNIEnv *, jobject, jmethodID, ...);
    jbyte   (*CallByteMethodV)(JNIEnv *, jobject, jmethodID, va_list);
    jbyte   (*CallByteMethodA)(JNIEnv *, jobject, jmethodID, const jvalue *);
    jchar   (*CallCharMethod)(JNIEnv *, jobject, jmethodID, ...);
    jchar   (*CallCharMethodV)(JNIEnv *, jobject, jmethodID, va_list);
    jchar   (*CallCharMethodA)(JNIEnv *, jobject, jmethodID, const jvalue *);
    jshort  (*CallShortMethod)(JNIEnv *, jobject, jmethodID, ...);
    jshort  (*CallShortMethodV)(JNIEnv *, jobject, jmethodID, va_list);
    jshort  (*CallShortMethodA)(JNIEnv *, jobject, jmethodID, const jvalue *);
    jint    (*CallIntMethod)(JNIEnv *, jobject, jmethodID, ...);
    jint    (*CallIntMethodV)(JNIEnv *, jobject, jmethodID, va_list);
    jint    (*CallIntMethodA)(JNIEnv *, jobject, jmethodID, const jvalue *);
    jlong   (*CallLongMethod)(JNIEnv *, jobject, jmethodID, ...);
    jlong   (*CallLongMethodV)(JNIEnv *, jobject, jmethodID, va_list);
    jlong   (*CallLongMethodA)(JNIEnv *, jobject, jmethodID, const jvalue *);
    jfloat  (*CallFloatMethod)(JNIEnv *, jobject, jmethodID, ...);
    jfloat  (*CallFloatMethodV)(JNIEnv *, jobject, jmethodID, va_list);
    jfloat  (*CallFloatMethodA)(JNIEnv *, jobject, jmethodID, const jvalue *);
    jdouble (*CallDoubleMethod)(JNIEnv *, jobject, jmethodID, ...);
    jdouble (*CallDoubleMethodV)(JNIEnv *, jobject, jmethodID, va_list);
    jdouble (*CallDoubleMethodA)(JNIEnv *, jobject, jmethodID, const jvalue *);
    void    (*CallVoidMethod)(JNIEnv *, jobject, jmethodID, ...);
    void    (*CallVoidMethodV)(JNIEnv *, jobject, jmethodID, va_list);
    void    (*CallVoidMethodA)(JNIEnv *, jobject, jmethodID, const jvalue *);
    /* 后面还有一大堆 nonvirtual/field/static/array 函数，
       我们只用到 GetStaticMethodID / CallStaticObjectMethod / GetArrayLength /
       GetObjectArrayElement / NewStringUTF / GetStringUTFChars，
       它们的位置在下面补齐 */
    void *fill0[30];   /* CallNonvirtual{Object..Void}Method V A = 10*3 = 30 项 */
    void *fill1[10];   /* GetFieldID + 9 个 GetXXXField */
    void *fill2[9];    /* 9 个 SetXXXField */
    jmethodID (*GetStaticMethodID)(JNIEnv *, jclass, const char *, const char *);
    jobject (*CallStaticObjectMethod)(JNIEnv *, jclass, jmethodID, ...);
    jobject (*CallStaticObjectMethodV)(JNIEnv *, jclass, jmethodID, va_list);
    jobject (*CallStaticObjectMethodA)(JNIEnv *, jclass, jmethodID, const jvalue *);
    jboolean(*CallStaticBooleanMethod)(JNIEnv *, jclass, jmethodID, ...);
    jboolean(*CallStaticBooleanMethodV)(JNIEnv *, jclass, jmethodID, va_list);
    jboolean(*CallStaticBooleanMethodA)(JNIEnv *, jclass, jmethodID, const jvalue *);
    void *fill3[24];   /* CallStatic{Byte,Char,Short,Int,Long,Float,Double,Void}Method V A = 8*3 */
    jmethodID (*GetStaticFieldID)(JNIEnv *, jclass, const char *, const char *);
    jobject (*GetStaticObjectField)(JNIEnv *, jclass, void *);
    void *fill4[17];   /* 其余 Set StaticXXXField */
    jstring (*NewString)(JNIEnv *, const jchar *, jsize);
    jsize   (*GetStringLength)(JNIEnv *, jstring);
    const jchar *(*GetStringChars)(JNIEnv *, jstring, jboolean *);
    void    (*ReleaseStringChars)(JNIEnv *, jstring, const jchar *);
    jstring (*NewStringUTF)(JNIEnv *, const char *);
    jsize   (*GetStringUTFLength)(JNIEnv *, jstring);
    const char *(*GetStringUTFChars)(JNIEnv *, jstring, jboolean *);
    void    (*ReleaseStringUTFChars)(JNIEnv *, jstring, const char *);
    jsize   (*GetArrayLength)(JNIEnv *, jarray);
    jobjectArray (*NewObjectArray)(JNIEnv *, jsize, jclass, jobject);
    jobject (*GetObjectArrayElement)(JNIEnv *, jobjectArray, jsize);
    void    (*SetObjectArrayElement)(JNIEnv *, jobjectArray, jsize, jobject);
};

struct JNIInvokeInterface_;
typedef const struct JNIInvokeInterface_ *JavaVM;
struct JNIInvokeInterface_ {
    void *reserved0, *reserved1, *reserved2;
    jint (*DestroyJavaVM)(JavaVM *);
    jint (*AttachCurrentThread)(JavaVM *, void **, void *);
    jint (*DetachCurrentThread)(JavaVM *);
    jint (*GetEnv)(JavaVM *, void **, jint);
    jint (*AttachCurrentThreadAsDaemon)(JavaVM *, void **, void *);
};

#define JNI_VERSION_1_6  0x00010006
#define JNI_OK           0
#define JNI_EDETACHED   (-2)

/* ---------------- 探测结果 ---------------- */
static struct res g_res;
static int g_stepfd = -1;

static void stepf(int n, const char *msg) {
    char b[192];
    int len;
    if (g_stepfd < 0) return;
    len = snprintf(b, sizeof(b), "%d %s\n", n, msg);
    lseek(g_stepfd, 0, SEEK_SET);
    (void)!write(g_stepfd, b, (size_t)len);
    fsync(g_stepfd);
}

struct res {
    int step;            /* 最后完成的步骤号 */
    int vm_ok, env_ok, app_ok, usb_ok, ndev, found, has_perm, conn_ok, fd;
    int vid, pid;
    char msg[256];
};

#define ST_FAIL(n, s) do { r.step = (n); snprintf(r.msg, sizeof(r.msg), "%s", (s)); \
                           g_res = r; stepf(r.step, r.msg); return; } while (0)
#define ST_OK(n, s)   do { r.step = (n); snprintf(r.msg, sizeof(r.msg), "%s", (s)); \
                           g_res = r; stepf(r.step, r.msg); } while (0)

static int check_exc(JNIEnv *env, const char *where, struct res *pr, int outfd) {
    jobject th = (*env)->ExceptionOccurred(env);
    if (!th) return 0;
    (*env)->ExceptionDescribe(env);
    (*env)->ExceptionClear(env);
    snprintf(pr->msg, sizeof(pr->msg), "exception at %s", where);
    return 1;
}

static void probe_child(int outfd) {
    struct res r;
    void *h;
    jint (*get_vms)(JavaVM **, jsize, jsize *);
    JavaVM *vm = NULL;
    JNIEnv *env = NULL;
    jsize nvm = 0;
    jclass cls;
    jmethodID mid;
    jobject app, usb, map, coll, arr;
    jsize n, i;

    memset(&r, 0, sizeof(r));
    ST_OK(0, "start");

    h = dlopen("libart.so", RTLD_NOW);
    if (!h) h = dlopen("libnativehelper.so", RTLD_NOW);
    if (!h) ST_FAIL(1, dlerror());
    get_vms = (jint (*)(JavaVM **, jsize, jsize *))dlsym(h, "JNI_GetCreatedJavaVMs");
    if (!get_vms) ST_FAIL(2, "no JNI_GetCreatedJavaVMs");
    if (get_vms(&vm, 1, &nvm) != 0 || !vm || nvm < 1) ST_FAIL(3, "JNI_GetCreatedJavaVMs failed");
    r.vm_ok = 1; ST_OK(4, "vm ok");

    if ((*vm)->GetEnv(vm, (void **)&env, JNI_VERSION_1_6) == JNI_EDETACHED) {
        if ((*vm)->AttachCurrentThread(vm, (void **)&env, NULL) != 0)
            ST_FAIL(5, "AttachCurrentThread failed");
    }
    if (!env) ST_FAIL(6, "null env");
    r.env_ok = 1; ST_OK(7, "env ok");

    /* 单独验证 NewStringUTF（它位于结构体靠后的位置，先确认偏移没错） */
    {
        jstring t = (*env)->NewStringUTF(env, "usb");
        if (!t) ST_FAIL(70, "NewStringUTF null");
        ST_OK(71, "NewStringUTF ok");
    }

    cls = (*env)->FindClass(env, "android/app/ActivityThread");
    if (!cls || check_exc(env, "FindClass ActivityThread", &r, outfd)) ST_FAIL(8, "no ActivityThread");
    mid = (*env)->GetStaticMethodID(env, cls, "currentApplication", "()Landroid/app/Application;");
    if (!mid || check_exc(env, "currentApplication id", &r, outfd)) ST_FAIL(9, "no currentApplication");
    app = (*env)->CallStaticObjectMethod(env, cls, mid);
    if (!app || check_exc(env, "currentApplication call", &r, outfd)) ST_FAIL(10, "currentApplication null");
    r.app_ok = 1; ST_OK(11, "app ok");

    {
        jclass appcls = (*env)->GetObjectClass(env, app);
        if (!appcls) ST_FAIL(120, "GetObjectClass null");
        ST_OK(121, "GetObjectClass ok");
        mid = (*env)->GetMethodID(env, appcls, "getSystemService",
                                  "(Ljava/lang/String;)Ljava/lang/Object;");
        if (!mid) ST_FAIL(122, "no getSystemService");
        ST_OK(123, "GetMethodID ok");
        /* 对照测试：调用无害实例方法 toString()，验证 CallObjectMethod 本身 */
        {
            jmethodID ts = (*env)->GetMethodID(env, appcls, "toString", "()Ljava/lang/String;");
            jstring sv;
            if (!ts) ST_FAIL(130, "no toString");
            sv = (jstring)(*env)->CallObjectMethod(env, app, ts);
            if (!sv) ST_FAIL(131, "toString null");
            ST_OK(132, "CallObjectMethod toString ok");
            {
                const char *cs = (*env)->GetStringUTFChars(env, sv, NULL);
                if (cs) {
                    snprintf(r.msg, sizeof(r.msg), "app.toString=%s", cs);
                    r.step = 133;
                    (void)!write(outfd, &r, sizeof(r));
                    (*env)->ReleaseStringUTFChars(env, sv, cs);
                }
            }
        }
        /* 对照 A：带 String 参数的实例方法，验证"字符串参数"传递 */
        {
            jmethodID gp = (*env)->GetMethodID(env, appcls, "getFileStreamPath",
                                               "(Ljava/lang/String;)Ljava/io/File;");
            jstring arg;
            jobject fobj;
            if (!gp) ST_FAIL(140, "no getFileStreamPath");
            arg = (*env)->NewStringUTF(env, "probe");
            if (!arg) ST_FAIL(141, "arg null");
            fobj = (*env)->CallObjectMethod(env, app, gp, arg);
            if (!fobj) ST_FAIL(142, "getFileStreamPath null");
            ST_OK(143, "string-arg method ok");
        }
        /* 对照 B：用 Context.USB_SERVICE 静态字段拿 "usb" 字符串 */
        {
            jclass ctxcls = (*env)->FindClass(env, "android/content/Context");
            jfieldID fid;
            jstring usbstr;
            if (!ctxcls) ST_FAIL(150, "no Context class");
            fid = (*env)->GetStaticFieldID(env, ctxcls, "USB_SERVICE", "Ljava/lang/String;");
            if (!fid) ST_FAIL(151, "no USB_SERVICE field");
            usbstr = (jstring)(*env)->GetStaticObjectField(env, ctxcls, fid);
            if (!usbstr) ST_FAIL(152, "USB_SERVICE null");
            ST_OK(153, "USB_SERVICE field ok");

            /* 测试1：getSystemService("activity") —— 换个服务名，看是不是"任何服务都崩" */
            {
                jstring s2 = (*env)->NewStringUTF(env, "activity");
                jobject o2 = (*env)->CallObjectMethod(env, app, mid, s2);
                ST_OK(160, o2 ? "getSystemService(activity) ok" : "activity null");
            }
            /* 手动构造 UsbManager：ServiceManager.getService("usb")
               -> IUsbManager.Stub.asInterface -> new UsbManager(context, service) */
            {
                jmethodID gbc = (*env)->GetMethodID(env, appcls, "getBaseContext",
                                                    "()Landroid/content/Context;");
                jobject base, binder, svc;
                jclass smc, stubc, umc;
                jmethodID gs, ai, ctor;

                if (!gbc) ST_FAIL(164, "no getBaseContext");
                base = (*env)->CallObjectMethod(env, app, gbc);
                if (!base) ST_FAIL(165, "base context null");
                ST_OK(166, "base context ok");

                smc = (*env)->FindClass(env, "android.os.ServiceManager");
                if (!smc) ST_FAIL(172, "no ServiceManager class");
                ST_OK(173, "ServiceManager class ok");
                gs = (*env)->GetStaticMethodID(env, smc, "getService",
                                               "(Ljava/lang/String;)Landroid/os/IBinder;");
                if (!gs) ST_FAIL(174, "no ServiceManager.getService");
                ST_OK(175, "getService id ok");

                binder = (*env)->CallStaticObjectMethod(env, smc, gs, (*env)->NewStringUTF(env, "activity"));
                if (!binder) ST_FAIL(176, "activity binder null");
                ST_OK(177, "activity binder ok");

                binder = (*env)->CallStaticObjectMethod(env, smc, gs, (*env)->NewStringUTF(env, "usb"));
                if (!binder) ST_FAIL(178, "usb binder null");
                ST_OK(179, "usb binder ok");

                stubc = (*env)->FindClass(env, "android.hardware.usb.IUsbManager$Stub");
                if (!stubc) ST_FAIL(180, "no IUsbManager$Stub");
                ai = (*env)->GetStaticMethodID(env, stubc, "asInterface",
                                               "(Landroid/os/IBinder;)Landroid/hardware/usb/IUsbManager;");
                if (!ai) ST_FAIL(181, "no asInterface");
                svc = (*env)->CallStaticObjectMethod(env, stubc, ai, binder);
                if (!svc) ST_FAIL(182, "service null");
                ST_OK(183, "IUsbManager ok");

                umc = (*env)->FindClass(env, "android/hardware/usb/UsbManager");
                if (!umc) ST_FAIL(184, "no UsbManager class");
                ctor = (*env)->GetMethodID(env, umc, "<init>",
                                           "(Landroid/content/Context;Landroid/hardware/usb/IUsbManager;)V");
                if (!ctor) ST_FAIL(185, "no UsbManager ctor");
                usb = (*env)->NewObject(env, umc, ctor, base, svc);
                if (!usb) ST_FAIL(186, "UsbManager new failed");
                ST_OK(187, "UsbManager constructed ok");
            }
        }
        if (!usb || check_exc(env, "getSystemService usb", &r, outfd)) ST_FAIL(124, "usb manager null");
        ST_OK(125, "getSystemService ok");
    }
    r.usb_ok = 1; ST_OK(14, "usb manager ok");

    {
        jclass uc = (*env)->GetObjectClass(env, usb);
        mid = (*env)->GetMethodID(env, uc, "getDeviceList", "()Ljava/util/HashMap;");
        if (!mid) ST_FAIL(15, "no getDeviceList");
        map = (*env)->CallObjectMethod(env, usb, mid);
        if (!map) ST_FAIL(16, "device list null");
        mid = (*env)->GetMethodID(env, (*env)->GetObjectClass(env, map),
                                  "values", "()Ljava/util/Collection;");
        if (!mid) ST_FAIL(17, "no values()");
        coll = (*env)->CallObjectMethod(env, map, mid);
        if (!coll) ST_FAIL(18, "values null");
        mid = (*env)->GetMethodID(env, (*env)->GetObjectClass(env, coll),
                                  "toArray", "()[Ljava/lang/Object;");
        if (!mid) ST_FAIL(19, "no toArray()");
        arr = (*env)->CallObjectMethod(env, coll, mid);
        if (!arr) ST_FAIL(20, "toArray null");
    }

    n = (*env)->GetArrayLength(env, (jarray)arr);
    r.ndev = (int)n;
    ST_OK(21, "device list ok");

    for (i = 0; i < n; i++) {
        jobject dev = (*env)->GetObjectArrayElement(env, (jobjectArray)arr, i);
        jclass dc;
        jmethodID gv, gp;
        jint vid, pid;
        if (!dev) continue;
        dc = (*env)->GetObjectClass(env, dev);
        gv = (*env)->GetMethodID(env, dc, "getVendorId", "()I");
        gp = (*env)->GetMethodID(env, dc, "getProductId", "()I");
        if (!gv || !gp) continue;
        vid = (*env)->CallIntMethod(env, dev, gv);
        pid = (*env)->CallIntMethod(env, dev, gp);
        if (i == 0) { r.vid = (int)vid; r.pid = (int)pid; }
        if ((int)vid == 0x090c && (int)pid == 0x037c) {
            jmethodID hp, od, gfd;
            jboolean has;
            jobject conn;
            jint fd;

            r.found = 1;
            r.vid = (int)vid; r.pid = (int)pid;
            ST_OK(22, "camera device found");

            hp = (*env)->GetMethodID(env, (*env)->GetObjectClass(env, usb),
                                     "hasPermission", "(Landroid/hardware/usb/UsbDevice;)Z");
            if (!hp) ST_FAIL(23, "no hasPermission");
            has = (*env)->CallBooleanMethod(env, usb, hp, dev);
            r.has_perm = (int)has;
            ST_OK(24, has ? "hasPermission=true" : "hasPermission=false");

            /* 没有权限就现场申请：Intent + PendingIntent.getBroadcast + requestPermission */
            if (!has) {
                jclass intentc = (*env)->FindClass(env, "android/content/Intent");
                jclass pic = (*env)->FindClass(env, "android/app/PendingIntent");
                jmethodID ictor, gb, rq;
                jobject intent, pi;
                int k = 0;

                if (!intentc || !pic) ST_FAIL(240, "no Intent/PendingIntent class");
                ST_OK(241, "classes ok");
                ictor = (*env)->GetMethodID(env, intentc, "<init>", "(Ljava/lang/String;)V");
                if (!ictor) ST_FAIL(242, "no Intent ctor");
                intent = (*env)->NewObject(env, intentc, ictor,
                                           (*env)->NewStringUTF(env, "com.abilix.controller.USB_PERMISSION"));
                if (!intent) ST_FAIL(243, "intent null");
                ST_OK(244, "intent ok");

                gb = (*env)->GetStaticMethodID(env, pic, "getBroadcast",
                        "(Landroid/content/Context;ILandroid/content/Intent;I)Landroid/app/PendingIntent;");
                if (!gb) ST_FAIL(245, "no getBroadcast");
                pi = (*env)->CallStaticObjectMethod(env, pic, gb, app, 0, intent, 0);
                if (!pi) ST_FAIL(246, "pendingintent null");
                ST_OK(247, "pendingintent ok");

                rq = (*env)->GetMethodID(env, (*env)->GetObjectClass(env, usb),
                        "requestPermission",
                        "(Landroid/hardware/usb/UsbDevice;Landroid/app/PendingIntent;)V");
                if (!rq) ST_FAIL(248, "no requestPermission");
                (*env)->CallVoidMethod(env, usb, rq, dev, pi);
                if (check_exc(env, "requestPermission", &r, outfd))
                    ST_FAIL(252, "requestPermission threw exception");
                ST_OK(249, "requestPermission sent（请在机器人屏幕点允许）");

                for (k = 0; k < 120; k++) {          /* 最多等 60 秒 */
                    usleep(500000);
                    if ((*env)->CallBooleanMethod(env, usb, hp, dev)) break;
                }
                has = (k < 120);
                r.has_perm = (int)has;
                ST_OK(250, has ? "permission granted" : "permission timeout");
                if (!has) ST_FAIL(251, "permission denied/timeout");
            }

            od = (*env)->GetMethodID(env, (*env)->GetObjectClass(env, usb),
                                     "openDevice",
                                     "(Landroid/hardware/usb/UsbDevice;)Landroid/hardware/usb/UsbDeviceConnection;");
            if (!od) ST_FAIL(25, "no openDevice");
            conn = (*env)->CallObjectMethod(env, usb, od, dev);
            if (!conn || check_exc(env, "openDevice", &r, outfd)) ST_FAIL(26, "openDevice null");
            r.conn_ok = 1; ST_OK(27, "connection ok");

            gfd = (*env)->GetMethodID(env, (*env)->GetObjectClass(env, conn),
                                      "getFileDescriptor", "()I");
            if (!gfd) ST_FAIL(28, "no getFileDescriptor");
            fd = (*env)->CallIntMethod(env, conn, gfd);
            r.fd = (int)fd;
            if (fd < 0) ST_FAIL(29, "fd<0");
            {
                int d = dup((int)fd);
                r.fd = d;
                ST_OK(30, d >= 0 ? "dup fd ok" : "dup failed");
            }
            break;
        }
    }
    ST_OK(31, r.found ? "done" : "camera not found");
}

/* ---------------- 服务器 ---------------- */
static char g_rep[64 * 1024];
static int g_replen;
static int g_log = -1;

static int g_repfd = -1;
static char g_prev[48 * 1024];
static int g_prevlen;

static void rp(const char *fmt, ...) {
    va_list ap; int n;
    if (g_replen >= (int)sizeof(g_rep) - 1) return;
    va_start(ap, fmt);
    n = vsnprintf(g_rep + g_replen, sizeof(g_rep) - g_replen, fmt, ap);
    va_end(ap);
    if (n > 0) {
        g_replen += n; g_rep[g_replen] = 0;
        if (g_repfd >= 0) {
            (void)!write(g_repfd, g_rep + g_replen - n, (size_t)n);
            fsync(g_repfd);
        }
    }
}

static int run_probe(struct res *out) {
    memset(&g_res, 0, sizeof(g_res));
    probe_child(0);            /* 主进程内直接执行：binder 只有在这里才正常 */
    *out = g_res;
    return 0;
}

static void build_report(void) {
    struct res r;
    int rc;
    char prev[256];
    int pn = 0;
    g_replen = 0; g_rep[0] = 0;
    prev[0] = 0;
    if (g_stepfd >= 0) {
        lseek(g_stepfd, 0, SEEK_SET);
        pn = (int)read(g_stepfd, prev, sizeof(prev) - 1);
        if (pn < 0) pn = 0;
        prev[pn] = 0;
        while (pn > 0 && (prev[pn-1] == '\n' || prev[pn-1] == '\r')) prev[--pn] = 0;
    }
    if (g_repfd >= 0) { ftruncate(g_repfd, 0); lseek(g_repfd, 0, SEEK_SET); }
    rp("=== JNIPROBE v15 ===\n");
    rp("uid=%d pid=%d\n", (int)getuid(), (int)getpid());
    rp("上次运行停在: %s\n", pn > 0 ? prev : "(无记录)");
    rc = run_probe(&r);
    rp("probe rc=%d\n", rc);
    if (rc < 0) rp("  子进程被信号 %d (%s)\n", -rc, strsignal(-rc));
    rp("  step=%d msg=%s\n", r.step, r.msg);
    rp("  vm=%d env=%d app=%d usb=%d ndev=%d found=%d has_perm=%d conn=%d fd=%d\n",
       r.vm_ok, r.env_ok, r.app_ok, r.usb_ok, r.ndev, r.found, r.has_perm, r.conn_ok, r.fd);
    rp("  first dev vid=%04x pid=%04x\n", r.vid, r.pid);
    rp("=== END ===\n");
}

static int send_all(int fd, const char *buf, int len) {
    int off = 0;
    while (off < len) {
        int n = (int)send(fd, buf + off, (size_t)(len - off), 0);
        if (n <= 0) return -1;
        off += n;
    }
    return 0;
}

static int serve_client(int c) {
    char cmd[32]; int clen = 0;
    char head[128];
    int hn;
    Printf("PC connected\n");
    hn = snprintf(head, sizeof(head),
                  "=== PREV ===\n%s\n=== PREV-END ===\n", g_prevlen > 0 ? g_prev : "(无历史)");
    if (send_all(c, head, hn) != 0) return 0;
    for (;;) {
        fd_set rf; struct timeval tv; int r, n, i;
        FD_ZERO(&rf); FD_SET(c, &rf); tv.tv_sec = 1; tv.tv_usec = 0;
        r = select(c + 1, &rf, NULL, NULL, &tv);
        if (r < 0) { if (errno == EINTR) continue; break; }
        if (r == 0) continue;
        n = (int)recv(c, cmd + clen, sizeof(cmd) - clen - 1, 0);
        if (n <= 0) break;
        clen += n;
        for (i = 0; i < clen; i++) {
            if (cmd[i] == '\n') {
                cmd[i] = 0;
                if (cmd[0] == 'Q') return 1;
                if (cmd[0] == 'P' || cmd[0] == 'R') { build_report(); send_all(c, g_rep, g_replen); }
                clen = 0; i = -1;
            }
        }
    }
    return 0;
}

int Main(int argc, char **argv) {
    int s, on = 1; struct sockaddr_in addr;
    (void)argc; (void)argv;
    g_log = open("/sdcard/Abilix/tmp/jniprobe.log", O_WRONLY | O_CREAT | O_APPEND, 0644);
    g_stepfd = open("/sdcard/Abilix/tmp/jni_step.txt", O_RDWR | O_CREAT, 0644);
    g_repfd = open("/sdcard/Abilix/tmp/jni_rep.txt", O_RDWR | O_CREAT, 0644);
    g_prevlen = 0;
    if (g_stepfd >= 0) {
        char sb[256];
        int sn;
        lseek(g_stepfd, 0, SEEK_SET);
        sn = (int)read(g_stepfd, sb, sizeof(sb) - 1);
        if (sn > 0) {
            sb[sn] = 0;
            while (sn > 0 && (sb[sn - 1] == '\n' || sb[sn - 1] == '\r')) sb[--sn] = 0;
            g_prevlen += snprintf(g_prev + g_prevlen, sizeof(g_prev) - g_prevlen,
                                  "[上次停在 step] %s\n", sb);
        }
    }
    if (g_repfd >= 0) {
        int n;
        lseek(g_repfd, 0, SEEK_SET);
        n = (int)read(g_repfd, g_prev + g_prevlen, sizeof(g_prev) - g_prevlen - 1);
        if (n > 0) g_prevlen += n;
        g_prev[g_prevlen] = 0;
        lseek(g_repfd, 0, SEEK_END);
    }
    Printf("JNIPROBE ready\nport=9001\n");

    s = socket(AF_INET, SOCK_STREAM, 0);
    if (s < 0) return -1;
    (void)setsockopt(s, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(9001);
    if (bind(s, (struct sockaddr *)&addr, sizeof(addr)) < 0) { Printf("bind fail %d\n", errno); return -2; }
    if (listen(s, 4) < 0) return -3;

    for (;;) {
        fd_set rf; struct timeval tv; int r;
        FD_ZERO(&rf); FD_SET(s, &rf); tv.tv_sec = 1; tv.tv_usec = 0;
        r = select(s + 1, &rf, NULL, NULL, &tv);
        if (r > 0) {
            int c = (int)accept(s, NULL, NULL);
            if (c >= 0) { int q = serve_client(c); close(c); if (q) break; }
        }
    }
    close(s);
    return 0;
}
