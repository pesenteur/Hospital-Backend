import hashlib
import json
import os
import random
import string
import time
from _decimal import Decimal
from datetime import datetime, timedelta
import re

import django.db
from django.db.models import Q
import jwt
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from tool.logging_dec import logging_check
from .models import Department, Doctor, Notification, News, Vacancy, Patient, User, \
    MedicalRecord, Code, Appointment, Leave, Message, Payment, Schedule, Vacancy_setting
from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore

AppointmentStatus = ["待就医", "待就医", "已就医", "失约", "待支付"]


# Create your views here.

class DepartmentList(View):
    def get(self, request):
        type = []
        data = Department.objects.values('department_type').distinct()
        for obj in data:
            child = []
            b = Department.objects.filter(department_type=obj.get('department_type'))
            for c in b:
                child.append({
                    "id": c.department_id,
                    "name": c.department_name,
                    "introduction": c.department_introduction
                })
            type.append({
                "name": obj.get('department_type'),
                "children": child
            })
        response = {
            'result': "1",
            'data': type
        }
        return JsonResponse(response)


class DoctorList(View):

    def get(self, request):
        keyword = request.GET.get('keyWord')

        # Filter doctors by keyword if provided
        if keyword:
            doctors = Doctor.objects.filter(doctor_name__icontains=keyword)
        else:
            doctors = Doctor.objects.all()

        # Serialize doctor objects to JSON
        data = []
        for doctor in doctors:
            doctor_data = {
                'id': doctor.doctor_id,
                'name': doctor.doctor_name,
                'department': doctor.department_id.department_name,
                'image': doctor.doctor_image if doctor.doctor_image else None,
                'introduction': doctor.doctor_introduction,
                "phone_number": doctor.phone_number,
                "gender": doctor.doctor_gender
            }
            data.append(doctor_data)

        response = {
            'result': "1",
            'data': data
        }

        return JsonResponse(response)


class NotificationList(View):
    def post(self, request):
        notifications = Notification.objects.all().order_by("-notification_time", "-notification_id")
        total = len(notifications)
        offset = 1
        count = 10
        if request.body:
            json_str = request.body
            json_obj = json.loads(json_str)
            keys = json_obj.keys()
            if 'offset' in keys:
                offset = json_obj['offset']
            if 'count' in keys:
                count = json_obj['count']
        # Serialize notification objects to JSON
        if offset != -1:
            notifications = notifications[offset - 1:offset + count]
        data = []
        for notification in notifications:
            notification_data = {
                'id': notification.notification_id,
                "image": notification.image if notification.image else '',
                'title': notification.title,
                'date': notification.notification_time,
                "content": notification.content,
                "short_info": notification.short_info
            }
            data.append(notification_data)

        response = {
            'result': "1",
            'data': data,
            "count": count,
            "total": total
        }
        return JsonResponse(response)


class NotificationDetail(View):
    def get(self, request, notification_id):
        try:
            notification = Notification.objects.get(notification_id=notification_id)
            notification_data = {
                "id": notification.notification_id,
                "image": notification.image if notification.image else '',
                'title': notification.title,
                'date': notification.notification_time,
                "content": notification.content
            }
            return JsonResponse({"result": "1", "data": notification_data})
        except:
            return JsonResponse({"result": "0", "message": "通知id不存在"})


class NewsList(View):
    def post(self, request):
        news = News.objects.all().order_by("-news_date", "news_id")
        total = len(news)
        json_str = request.body
        json_obj = json.loads(json_str)
        keys = json_obj.keys()
        if 'offset' in keys:
            offset = json_obj['offset']
        else:
            offset = 1
        if 'count' in keys:
            count = json_obj['count']
        else:
            count = 10
        if offset != -1:
            news = news[offset - 1:offset + count]
        # Serialize notification objects to JSON
        data = []
        for new in news:
            news_data = {
                'id': new.news_id,
                "image": new.image if new.image else None,
                'title': new.news_title,
                "content": new.news_content,
                "type": new.type,
                "date": new.news_date,
                "short_info":new.short_info
            }
            data.append(news_data)

        response = {
            'result': "1",
            'data': data,
            "count": count,
            "total": total
        }
        return JsonResponse(response)


class NewsDetail(View):
    def get(self, request, news_id):
        try:
            new = News.objects.get(news_id=news_id)
            news_data = {
                'id': new.news_id,
                "image": new.image if new.image else None,
                'title': new.news_title,
                "content": new.news_content,
                "type": new.type,
                "date": new.news_date
            }
            return JsonResponse({"result": "1", "data": news_data})
        except:
            return JsonResponse({"result": "0", "message": "新闻id不存在"})


class DoctorDetail(View):
    def get(self, request, doctor_id):
        try:
            doctor = Doctor.objects.get(doctor_id=doctor_id)
            vacancies = Vacancy.objects.filter(doctor_id_id=doctor_id)
            available = set()
            for vacancy in vacancies:
                today = datetime.now().replace(hour=23, minute=0, second=0, microsecond=0)
                if vacancy.start_time>today:
                    available.add(vacancy.start_time.strftime("%Y-%m-%d"))
            available = sorted(list(available))
            data = {
                "id": doctor.doctor_id,
                "name": doctor.doctor_name,
                "department": doctor.department_id.department_name,
                'image': doctor.doctor_image if doctor.doctor_image else None,
                "introduction": doctor.doctor_introduction,
                "available": available
            }
            response = {
                "result": "1",
                "data": data
            }
            return JsonResponse(response)
        except Doctor.DoesNotExist:
            response = {
                "result": "0",
                "message": "医生不存在"
            }
            return JsonResponse(response)


class CarouselMapList(View):
    def get(self, request):
        notifications = Notification.objects.filter(type=1)
        newsList = News.objects.filter(type=1)
        # Serialize notification objects to JSON
        data = []
        for notification in notifications:
            data.append({
                "id": notification.notification_id,
                "img": notification.image if notification.image else None,
                "time": notification.notification_time.strftime("%Y-%m-%d"),
                "title": notification.title,
                "content": notification.content
            })
        for news in newsList:
            data.append({
                "id": news.news_id,
                "img": news.image if news.image else None,
                "time": news.news_date.strftime("%Y-%m-%d"),
                "title": news.news_title,
                "content": news.news_content
            })
        response = {
            'result': "1",
            'data': data
        }
        return JsonResponse(response)


class VacancyList(View):
    def get(self, request):
        data = []
        departmentId = request.GET.get('department')
        date = request.GET.get('date')
        doctor_id_list = Vacancy.objects.filter(start_time__contains=date).values('doctor_id').distinct()
        for doctor_id in doctor_id_list:
            doctor_id = doctor_id['doctor_id']
            doctor_info = Doctor.objects.get(doctor_id=doctor_id)
            print(doctor_info.department_id_id)
            print(departmentId)
            if int(doctor_info.department_id_id) != int(departmentId):
                continue
            vacancies = Vacancy.objects.filter(start_time__contains=date, doctor_id=doctor_id).values('vacancy_count',
                                                                                                      'start_time')
            available = []
            morning_cnt = 0
            afternoon_cnt = 0
            morning_judge = False
            afternoon_judge = False
            for vacancy in vacancies:
                if vacancy['start_time'].hour < 12:
                    morning_cnt += vacancy['vacancy_count']
                    morning_judge = True
                else:
                    afternoon_cnt += vacancy['vacancy_count']
                    afternoon_judge = True
            if morning_judge:
                available.append({"is_morning": True, "time": date, "num": morning_cnt})
            if afternoon_judge:
                available.append({"is_morning": False, "time": date, "num": afternoon_cnt})
            data.append({
                "id": doctor_id,
                "name": doctor_info.doctor_name,
                "department": Department.objects.get(department_id=departmentId).department_name,
                "image": doctor_info.doctor_image if doctor_info.doctor_image else None,
                "introduction": doctor_info.doctor_introduction,
                "available": available
            })

        response = {
            "result": "1",
            "data": data,
        }
        return JsonResponse(response)


class UploadAvatar(View):
    @method_decorator(logging_check)
    def post(self, request):
        token = request.META.get('HTTP_AUTHORIZATION')
        jwt_token = jwt.decode(token, settings.JWT_TOKEN_KEY, algorithms='HS256')
        user_id = User.objects.get(phone_number=jwt_token['username']).user_id
        user = User.objects.get(user_id=user_id)
        image_file = request.FILES.get('avatar').open('r')
        md5 = hashlib.md5(image_file.read()).hexdigest()
        extra_name = image_file.name.split('.')[-1]
        file_name = md5 + '.' + extra_name
        if not os.path.exists(f'./media/{file_name}'):
            image_file.seek(0)
            with open(f'./media/{md5}.{extra_name}', 'wb') as f:
                f.write(image_file.read())
        user.avatar = f'./{md5}.{extra_name}'
        user.save()
        return JsonResponse({'result': "1", 'message': '上传头像成功！'})


class VacancyDetail(View):
    def get(self, request):
        try:
            data = []
            doctor_id = request.GET.get('doctor_id')
            date = request.GET.get('date')
            is_morning = int(request.GET.get('is_morning'))

            vacancies = Vacancy.objects.filter(start_time__contains=date, doctor_id=doctor_id)
            for vacancy in vacancies:
                if (vacancy.start_time.hour < 12 and is_morning == 1) or (
                        vacancy.start_time.hour > 12 and is_morning == 0):
                    info = {
                        "vacancy_id": vacancy.vacancy_id,
                        "start_time": vacancy.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "end_time": vacancy.end_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "count": vacancy.vacancy_count,
                        "left": vacancy.vacancy_left
                    }
                    data.append(info)
            response = {
                "result": "1",
                "message":"成功获取放号的具体信息",
                "data": data
            }
            return JsonResponse(response)
        except:
            return JsonResponse({
                "result": "0",
                "message":"出错了"
            })


class PatientList(View):
    @method_decorator(logging_check)
    def get(self, request):
        try:
            token = request.META.get('HTTP_AUTHORIZATION')
            jwt_token = jwt.decode(token, settings.JWT_TOKEN_KEY, algorithms='HS256')
            user_id = User.objects.get(phone_number=jwt_token['username']).user_id
            data = []
            patients = Patient.objects.filter(user_id=user_id).values('patient_gender', 'patient_name', 'phone_number',
                                                                      'identification', 'absence', 'address',
                                                                      'patient_id')
            for patient in patients:
                info = {
                    "id": patient['patient_id'],
                    "name": patient['patient_name'],
                    "gender": patient['patient_gender'],
                    "identification": patient['identification'],
                    "phone": patient['phone_number'],
                    "cnt": patient['absence'],
                    'address': patient['address'],
                }

                data.append(info)
            response = {
                "result": "1",
                "data": data
            }
            return JsonResponse(response)
        except:
            response = {
                "result": "0"
            }
            return JsonResponse(response)


class PatientWaiting(View):
    @method_decorator(logging_check)
    def get(self, request):
        token = request.META.get('HTTP_AUTHORIZATION')
        jwt_token = jwt.decode(token, settings.JWT_TOKEN_KEY, algorithms='HS256')
        user_id = User.objects.get(phone_number=jwt_token['username']).user_id
        user = User.objects.get(user_id=user_id)
        if user.type == "doctor":
            appointment_finished = []
            appointment_unfinished = []
            doctor_id = Doctor.objects.filter(phone_number=user.phone_number).first().doctor_id
            doctor = Doctor.objects.get(doctor_id=doctor_id)
            # 获取当前日期
            current_date = datetime.today()
            # 检索医生当天正在等待或已完成的预约
            waiting_appointments = Appointment.objects.filter(
                Q(doctor_id=doctor),
                Q(appointment_time__date=current_date),
                Q(appointment_status=0) | Q(appointment_status=1) | Q(appointment_status=2)
            ).order_by('appointment_status', 'appointment_id')
            for appointment in waiting_appointments:
                patient = Patient.objects.get(patient_id=appointment.patient_id_id)
                info = {
                    "patient_id": patient.patient_id,
                    "patient_name": patient.patient_name,
                    "appointment_status": AppointmentStatus[appointment.appointment_status]
                }
                if appointment.appointment_status == 0 or appointment.appointment_status == 1:
                    appointment_unfinished.append(info)
                else:
                    appointment_finished.append(info)
            response = {
                "result": "1",
                "message":"成功拿到等待患者的信息",
                "appointment_finished": appointment_finished,
                "appointment_unfinished": appointment_unfinished
            }
            return JsonResponse(response)
        else:
            return JsonResponse({"result": "0", "message": "用户未有权限！"})


class LeaveList(View):
    @method_decorator(logging_check)
    def get(self, request):
        # try:
        data = []
        token = request.META.get('HTTP_AUTHORIZATION')
        jwt_token = jwt.decode(token, settings.JWT_TOKEN_KEY, algorithms='HS256')
        user_id = User.objects.get(phone_number=jwt_token['username']).user_id
        user = User.objects.get(user_id=user_id)
        if user.type == "doctor":
            doctor_id = Doctor.objects.filter(phone_number=user.phone_number).first().doctor_id
            leaves = Leave.objects.filter(doctor_id=doctor_id)
            for leave in leaves:
                info = {
                    "leave_id": leave.leave_id,
                    "start_time": leave.start_time.strftime("%Y-%m-%d %H:%M"),
                    "end_time": leave.end_time.strftime("%Y-%m-%d %H:%M"),
                    "type": leave.type,
                    "reason": leave.reseon,
                    "leave_status": leave.leave_status
                }
                data.append(info)
            response = {
                "result": "1",
                "message":"成功获取请假列表",
                "data": data
            }
            return JsonResponse(response)
        else:
            return JsonResponse({"result": 0, "message": "用户未有权限"})


class UserInfo(View):
    @method_decorator(logging_check)
    def get(self, request):
        try:
            token = request.META.get('HTTP_AUTHORIZATION')
            jwt_token = jwt.decode(token, settings.JWT_TOKEN_KEY, algorithms='HS256')
            user_id = User.objects.get(phone_number=jwt_token['username']).user_id
            user = User.objects.get(user_id=user_id)
            info = {
                "user_id": user_id,
                "phone": user.phone_number,
                "type": user.type,
                "avatar": request.build_absolute_uri(user.avatar.url) if user.avatar else None
            }
            response = {
                "result": "1",
                "data": info
            }
            return JsonResponse(response)
        except:
            response = {
                "result": "0",
                "message": "出错啦！"
            }
            return JsonResponse(response)


def generate_verification_code():
    characters = string.digits
    code = ''.join(random.choice(characters) for _ in range(6))
    return code


class SendCode(View):
    def get(self, request, phone_number):
        verification_code = generate_verification_code()
        date_time = datetime.now()
        if is_illegal_phoneNumber(phone_number):
            return JsonResponse(
                {"result": "0", 'message': '手机号码不合法'})
        info = Code.objects.filter(phone_number=phone_number).first()
        if info is None:
            pass
        else:
            Code.delete(info)
        code = Code(
            verification_code=verification_code,
            phone_number=phone_number,
            create_time=date_time,
            expire_time=date_time + timedelta(minutes=30)
        )
        code.save()
        return JsonResponse(
            {"result": "1", 'message': '验证码发送成功', "vertification_code": verification_code})


class LoginPassWd(View):
    def post(self, request):
        token = request.META.get('HTTP_AUTHORIZATION')
        if token is None:
            json_str = request.body
            json_obj = json.loads(json_str)
            phone_number = json_obj['phone_number']
            passwd = json_obj['password']
            m = hashlib.md5()
            m.update(passwd.encode())
            md5_pwd = m.hexdigest()
            user = User.objects.filter(phone_number=phone_number).first()
            if user is None:
                response = {
                    "result": "0",
                    "message": "用户不存在"
                }
                return JsonResponse(response)
            else:
                if user.passwd == md5_pwd:
                    token = make_token(phone_number)
                    response = {
                        "result": "1",
                        "message": "登录成功",
                        "data": {"token": token}
                    }
                    return JsonResponse(response)
                else:
                    response = {
                        "result": "0",
                        "message": "密码错误"
                    }
                    return JsonResponse(response)
        else:
            try:
                jwt_token = jwt.decode(token, settings.JWT_TOKEN_KEY, algorithms='HS256')
                response = {
                    "result": "0",
                    "message": "已登录，请勿重复登录"
                }
                return JsonResponse(response)
            except:
                response = {
                    "result": "0",
                    "message": "登录状态异常"
                }
                return JsonResponse(response, status=401)


class BackPassword(View):
    def post(self, request):
        json_str = request.body
        json_obj = json.loads(json_str)
        phone_number = json_obj['phone_number']
        vertification_code = json_obj['vertification_code']
        new_passwd = json_obj['new_password']
        m = hashlib.md5()
        m.update(new_passwd.encode())
        md5_pwd = m.hexdigest()
        user = User.objects.filter(phone_number=phone_number).first()
        code = Code.objects.filter(phone_number=phone_number).first()
        if user is None:
            return JsonResponse({"result": "0", "message": "该用户不存在"})
        else:
            if code.verification_code == vertification_code:
                user.passwd = md5_pwd
                user.save()
                return JsonResponse({"result": "1", "message": "修改成功"})
            else:
                return JsonResponse({"result": "0", "message": "密码错误"})


class ChangePassword(View):
    @method_decorator(logging_check)
    def post(self, request):
        token = request.META.get('HTTP_AUTHORIZATION')
        jwt_token = jwt.decode(token, settings.JWT_TOKEN_KEY, algorithms='HS256')
        json_str = request.body
        json_obj = json.loads(json_str)
        phone_number = jwt_token['username']
        new_passwd = json_obj['new_password']
        old_passwd = json_obj['old_password']
        m = hashlib.md5()
        m.update(old_passwd.encode())
        md5_pwd = m.hexdigest()
        user = User.objects.filter(phone_number=phone_number).first()

        if user is None:
            return JsonResponse({"result": "0", "message": "该用户不存在"})
        else:
            if md5_pwd == user.passwd:
                m = hashlib.md5()
                m.update(new_passwd.encode())
                md5_pwd = m.hexdigest()
                user.passwd = md5_pwd
                user.save()
                return JsonResponse({"result": "1", "message": "修改成功"})
            else:
                return JsonResponse({"result": "0", "message": "密码错误"})


class ChangePhone(View):
    @method_decorator(logging_check)
    def post(self, request):
        token = request.META.get('HTTP_AUTHORIZATION')
        jwt_token = jwt.decode(token, settings.JWT_TOKEN_KEY, algorithms='HS256')
        json_str = request.body
        json_obj = json.loads(json_str)
        phone_number = jwt_token['username']
        new_phone_number = json_obj['new_phone_number']
        vertification_code = json_obj['vertification_code']
        user = User.objects.filter(phone_number=phone_number).first()
        code = Code.objects.filter(phone_number=new_phone_number).first()
        if code is None:
            return JsonResponse({"result": "0", "message": "未发送验证码"})
        if user is None:
            return JsonResponse({"result": "0", "message": "该用户不存在"})
        else:
            if code.verification_code == vertification_code:
                user.phone_number = new_phone_number
                user.save()
                if user.type == "doctor":
                    doctor = Doctor.objects.filter(phone_number=phone_number).first()
                    doctor.phone_number = new_phone_number
                    doctor.save()
                return JsonResponse({"result": "1", "message": "修改成功", "token": make_token(new_phone_number)})
            else:
                return JsonResponse({"result": "0", "message": "验证码错误"})


class LoginCode(View):
    def post(self, request):
        token = request.META.get('HTTP_AUTHORIZATION')
        if token is None:
            json_str = request.body
            json_obj = json.loads(json_str)
            phone_number = json_obj['phone_number']
            if User.objects.filter(phone_number=phone_number).first() is None:
                return JsonResponse({"result": "0", "message": "用户不存在"})
            code = json_obj['code']
            data_code = Code.objects.filter(phone_number=phone_number).first()
            if data_code is None:
                response = {
                    "result": "0",
                    "message": "请先获取验证码"
                }
                return JsonResponse(response)
            else:
                if code == data_code.verification_code:
                    token = make_token(phone_number)
                    print(token)
                    Code.objects.filter(phone_number=phone_number).first().delete()
                    response = {
                        "result": "1",
                        "data": {"token": token}
                    }
                    return JsonResponse(response)
                else:
                    response = {
                        "result": "0",
                        "message": "验证码错误"
                    }
                    return JsonResponse(response)
        else:
            try:
                jwt_token = jwt.decode(token, settings.JWT_TOKEN_KEY, algorithms='HS256')
                response = {
                    "result": "0",
                    "message": "已登录，请勿重复登录"
                }
                return JsonResponse(response)
            except:
                response = {
                    "result": "0",
                    "message": "登录状态异常"
                }
                return JsonResponse(response, status=401)


def make_token(username, expire=3600 * 24):
    key = settings.JWT_TOKEN_KEY
    now_t = time.time()
    payload_data = {'username': username, 'exp': now_t + expire}
    return jwt.encode(payload_data, key, algorithm='HS256')


class UserView(View):
    def post(self, request):
        json_str = request.body
        json_obj = json.loads(json_str)
        phone_number = json_obj['phone_number']
        password = json_obj['password']
        verification_code = json_obj['verification_code']
        info = Code.objects.filter(phone_number=phone_number).first()
        user = User.objects.filter(phone_number=phone_number).first()
        if user is not None:
            return JsonResponse({'result': "0", 'message': '手机号已经被注册'})
        if info is not None:
            info = Code.objects.get(phone_number=phone_number)
            end_time = info.expire_time
            if datetime.now() > end_time:
                return JsonResponse({'result': "0", 'message': "验证码过期"})
            m = hashlib.md5()
            m.update(password.encode())
            md5_pwd = m.hexdigest()
            if info.verification_code == verification_code:
                user = User(
                    phone_number=phone_number,
                    passwd=md5_pwd,
                    type="user"
                )
                user.save()
                return JsonResponse({'result': "1", 'message': '注册成功'})
            else:
                return JsonResponse({'result': "0", 'message': "验证码错误"})
        else:
            return JsonResponse({'result': "0", 'message': '未发送验证码'})


class PatientDetail(View):
    @method_decorator(logging_check)
    def get(self, request, patient_id):
        patient = Patient.objects.get(patient_id=patient_id)
        response = {"result": "1",
                    "data": {
                        "id": patient.patient_id,
                        "name": patient.patient_name,
                        "gender": patient.patient_gender,
                        "cnt": patient.absence,
                        "address": patient.address,
                        "age": patient.age,
                        "phone": patient.phone_number,
                        "identification": patient.identification
                    }}
        return JsonResponse(response)


class PaymentList(View):
    def get(self, request, appointment_id):
        payment = Payment.objects.filter(appointment_id_id=appointment_id).first()
        if payment:
            return JsonResponse({"result": "1", "data": {
                "payment_status": payment.payment_status,
                "payment_id": payment.payment_id,
                "payment_amount": payment.amount
            }})


class Pay(View):
    def post(self, request, payment_id):
        pay = Payment.objects.get(payment_id=payment_id)
        pay.payment_status = '已支付'
        pay.save()
        appointment = Appointment.objects.get(appointment_id=pay.appointment_id_id)

        patient = Patient.objects.get(patient_id=appointment.patient_id_id)
        doctor = Doctor.objects.get(doctor_id=appointment.doctor_id_id)
        department = Department.objects.get(department_id=doctor.department_id_id)
        users = User.objects.filter(patient__patient_id=patient.patient_id)

        appointment.appointment_status = 0
        appointment.save()
        for user in users:
            message = Message(
                title="您的预约成功",
                content=
f"""尊敬的{patient.patient_name}患者，
感谢您选择我们医院进行就诊。您的预约已成功确认。以下是预约的详细信息：
预约时间：{appointment.appointment_time.strftime("%Y年%m月%d日 %H:%M")}
医生姓名：{doctor.doctor_name}
科室：{department.department_name}
医院地址：北京市海淀区知春路29号
请您务必按照预约时间准时前来就诊。如果您有任何紧急情况或无法按时赴约，请提前联系我们的预约部门进行调整。
我们提醒您带齐所有相关的医疗资料和身份证件。如有需要，您可以提前到医院前台办理挂号手续。
如果您对预约有任何疑问或需要进一步的帮助，请随时联系我们的预约部门。
再次感谢您的信任，我们期待为您提供优质的医疗服务。
祝您健康！
医院预约部门
阳光医院
123-4567890""",
                message_time=datetime.now(),
                user_id_id=user.user_id,
                is_read=0
            )
            message.save()
        return JsonResponse({"result": "1", "message": "支付成功！"})


class GetPaymentStatus(View):
    def get(self, request, payment_id):
        pay = Payment.objects.get(payment_id=payment_id)
        return JsonResponse({"result": "1", "status": pay.payment_status})


class MakeAppointment(View):
    @method_decorator(logging_check)
    def post(self, request):
        json_str = request.body
        json_obj = json.loads(json_str)
        doctor_id = json_obj['doctor_id']
        start_time = json_obj['start_time']
        patient_id = json_obj['patient_id']
        appointment = Appointment.objects.filter(doctor_id_id=doctor_id, patient_id_id=patient_id,
                                                 appointment_time=start_time).first()
        if appointment:
            return JsonResponse({"result": "0", "message": "您已预约！"})
        vacancy = Vacancy.objects.filter(doctor_id_id=doctor_id, start_time=start_time).first()
        try:
            if vacancy.vacancy_left > 0:
                vacancy.vacancy_left = vacancy.vacancy_left - 1

                appointment = Appointment(
                    appointment_time=datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S"),
                    appointment_status=4,
                    doctor_id_id=doctor_id,
                    patient_id_id=patient_id
                )
                patient = Patient.objects.get(patient_id=patient_id)
                users = patient.user_id.all()

                doctor = Doctor.objects.get(doctor_id=doctor_id)
                department = Department.objects.get(department_id=doctor.department_id_id)
                appointment.save()
                print(type(appointment.appointment_time))
                for user in users:
                    print(user.user_id)

                appointment.save()
                payment = Payment(
                    payment_status="待支付",
                    amount=20,
                    appointment_id_id=appointment.appointment_id
                )
                payment.save()
                vacancy.save()
                return JsonResponse(
                    {"result": "1", "message": "预约成功！", "appointment_id": appointment.appointment_id,
                     "payment_id": payment.payment_id})
        except:
            return JsonResponse({"result": "0", "message": "出错了..."})


class CancelAppointment(View):
    # @method_decorator(logging_check)
    def post(self, request):
        json_str = request.body
        json_obj = json.loads(json_str)
        appointment_id = json_obj['appointment_id']
        appointment = Appointment.objects.filter(appointment_id=appointment_id).first()
        if appointment is None:
            return JsonResponse({"result": "0", "message": "该预约不存在！"})
        doctor_id = Appointment.objects.get(appointment_id=appointment_id).doctor_id_id
        start_time = Appointment.objects.get(appointment_id=appointment_id).appointment_time
        vacancy = Vacancy.objects.filter(doctor_id_id=doctor_id, start_time=start_time).first()
        try:
            vacancy.vacancy_left = vacancy.vacancy_left + 1
            appointment = Appointment.objects.get(appointment_id=appointment_id)
            patient = Patient.objects.get(patient_id=appointment.patient_id_id)
            doctor = Doctor.objects.get(doctor_id=appointment.doctor_id_id)
            department = Department.objects.get(department_id=doctor.department_id_id)
            users = patient.user_id.all()
            for user in users:
                message = Message(
                    title="您的预约取消成功",
                    content=f"""尊敬的{patient.patient_name}患者，
您的预约已成功取消。以下是取消预约的详细信息：
预约时间：{appointment.appointment_time.strftime("%Y年%m月%d日 %H:%M")}
医生姓名：{doctor.doctor_name}
科室：{department.department_name}
医院地址：北京市海淀区知春路29号
如果您有任何其他需求或需要进一步的帮助，请随时联系我们的预约部门。
再次感谢您的理解与支持。
祝您健康！
医院预约部门
阳光医院
123-4567890""",
                    message_time=datetime.now(),
                    user_id_id=user.user_id,
                    is_read=0
                )
                message.save()
            vacancy.save()
            Appointment.delete(appointment)
            return JsonResponse({"result": "1", "message": "取消预约成功！"})
        except:
            return JsonResponse({"result": "0", "message": "出错啦！"})


class MakeMedicalRecord(View):
    @method_decorator(logging_check)
    def post(self, request):
        token = request.META.get('HTTP_AUTHORIZATION')
        jwt_token = jwt.decode(token, settings.JWT_TOKEN_KEY, algorithms='HS256')
        user_id = User.objects.get(phone_number=jwt_token['username']).user_id
        user = User.objects.get(user_id=user_id)
        if user.type == 'doctor':
            json_str = request.body
            json_obj = json.loads(json_str)
            medical_record_date = json_obj['medical_record_date']
            patient_id = json_obj['patient_id']
            doctor = Doctor.objects.filter(phone_number=user.phone_number).first()
            doctor_id = doctor.doctor_id
            department_id = doctor.department_id_id
            symptom = json_obj['symptom']
            prescription = json_obj['prescription']
            result = json_obj['result']
            advice = json_obj['advice']
            try:
                medical_record = MedicalRecord.objects.filter(patient_id_id=patient_id, department_id_id=department_id,
                                                              doctor_id_id=doctor_id).first()
                appointment_id = Appointment.objects.filter(patient_id_id=patient_id, doctor_id_id=doctor_id).first(). \
                    appointment_id
                appointment = Appointment.objects.get(appointment_id=appointment_id)
                appointments = Appointment.objects.filter(appointment_id__lt=appointment.appointment_id,
                                                          appointment_status=0)
                for item in appointments:
                    item.appointment_status = 1
                appointment.appointment_status = 2
                appointment.save()
                if medical_record:
                    medical_record.medical_record_date = medical_record_date
                    medical_record.advice = advice
                    medical_record.result = result
                    medical_record.symptom = symptom
                    medical_record.prescription = prescription
                else:
                    medical_record = MedicalRecord(
                        medical_record_date=medical_record_date,
                        advice=advice,
                        result=result,
                        symptom=symptom,
                        prescription=prescription,
                        doctor_id_id=doctor_id,
                        patient_id_id=patient_id,
                        department_id_id=department_id,
                        appointment_id_id=appointment_id
                    )
                medical_record.save()
                return JsonResponse({"result": "1", "message": "开具处方成功！"})
            except:
                return JsonResponse({"result": "0", "message": "出错啦！"})
        else:
            return JsonResponse({"result": "0", "message": "未有权限"})


class MakeLeave(View):
    @method_decorator(logging_check)
    def post(self, request):
        token = request.META.get('HTTP_AUTHORIZATION')
        jwt_token = jwt.decode(token, settings.JWT_TOKEN_KEY, algorithms='HS256')
        user_id = User.objects.get(phone_number=jwt_token['username']).user_id
        user = User.objects.get(user_id=user_id)
        if user.type == 'doctor':
            doctor_id = Doctor.objects.filter(phone_number=jwt_token['username']).first().doctor_id
            json_str = request.body
            json_obj = json.loads(json_str)
            start_time = json_obj['start_time']
            end_time = json_obj['end_time']
            leave_type = json_obj['type']
            reason = json_obj['reason']
            try:
                leave = Leave(
                    doctor_id_id=doctor_id,
                    start_time=start_time,
                    end_time=end_time,
                    type=leave_type,
                    reseon=reason,
                    leave_status="申请中"
                )
                leave.save()
                return JsonResponse({"result": "1", "message": "请假申请成功！"})
            except:
                return JsonResponse({"result": "0", "message": "出错啦！"})
        else:
            return JsonResponse({"result": "0", "message": "用户未有权限"})


class CancelLeave(View):
    @method_decorator(logging_check)
    def delete(self, request):
        token = request.META.get('HTTP_AUTHORIZATION')
        jwt_token = jwt.decode(token, settings.JWT_TOKEN_KEY, algorithms='HS256')
        user_id = User.objects.get(phone_number=jwt_token['username']).user_id
        user = User.objects.get(user_id=user_id)
        if user.type == 'doctor':
            json_str = request.body
            json_obj = json.loads(json_str)
            leave_id = json_obj['leave_id']
            try:
                leave = Leave.objects.get(leave_id=leave_id)
                Leave.delete(leave)
                return JsonResponse({"result": "1", "message": "取消请假成功！"})
            except:
                return JsonResponse({"result": "0", "message": "出错啦！"})
        else:
            return JsonResponse({"result": "0", "message": "用户未有权限"})


class PatientAppointment(View):
    @method_decorator(logging_check)
    def get(self, request, patient_id):
        appointments = Appointment.objects.filter(patient_id_id=patient_id)
        data = []
        for appointment in appointments:
            doctor = Doctor.objects.get(doctor_id=appointment.doctor_id_id)
            department = Department.objects.get(department_id=doctor.department_id_id)
            appointment_time = appointment.appointment_time.strftime("%Y-%m-%d %H:%M")
            data.append({"appointment_id": appointment.appointment_id, "appointment_time": appointment_time,
                         "appointment_status": AppointmentStatus[appointment.appointment_status],
                         "doctor_name": doctor.
                        doctor_name,
                         "department_name": department.
                        department_name})
        return JsonResponse({"result": "1", "data": data})


class GetMedicalRecord(View):
    @method_decorator(logging_check)
    def get(self, request, patient_id):
        medical_records = MedicalRecord.objects.filter(patient_id_id=patient_id)
        patient = Patient.objects.get(patient_id=patient_id)
        data = []
        for medical_record in medical_records:
            doctor = Doctor.objects.get(doctor_id=medical_record.doctor_id_id)
            result = {
                "patient_id": patient.patient_id,
                "name": patient.patient_name,
                "gender": patient.patient_gender,
                "absence": patient.absence,
                "address": patient.address,
                "age": patient.age,
                "medical_record_id": medical_record.medical_record_id,
                "medical_record_date": medical_record.medical_record_date,
                "department_name": Department.objects.get(department_id=doctor.department_id_id).department_name,
                "doctor_name": doctor.doctor_name,
                "symptom": medical_record.symptom,
                "advice": medical_record.advice,
                "prescription": medical_record.prescription,
                "result": medical_record.result
            }
            data.append(result)
        return JsonResponse({"result": "1","message":"成功获取病历","data": data})


def calculate_age(id_card_number):
    birth_year = int(id_card_number[6:10])
    birth_month = int(id_card_number[10:12])
    birth_day = int(id_card_number[12:14])

    current_date = datetime.now()
    current_year = current_date.year
    current_month = current_date.month
    current_day = current_date.day

    age = current_year - birth_year

    # 检查是否已经过了生日
    if (current_month, current_day) < (birth_month, birth_day):
        age -= 1

    return age


def get_gender(id_card_number):
    gender_code = int(id_card_number[-2])
    if gender_code % 2 == 0:
        return "女"
    else:
        return "男"


class AddPatient(View):
    @method_decorator(logging_check)
    def post(self, request):
        json_str = request.body
        json_obj = json.loads(json_str)
        token = request.META.get('HTTP_AUTHORIZATION')
        jwt_token = jwt.decode(token, settings.JWT_TOKEN_KEY, algorithms='HS256')
        user_id = User.objects.get(phone_number=jwt_token['username']).user_id
        user = User.objects.get(user_id=user_id)
        patient_name = json_obj['patient_name']
        patient_identification = json_obj['identification']
        keys = json_obj.keys()
        if 'phone_number' in keys:
            phone_number = json_obj['phone_number']
        else:
            phone_number = None
        if 'address' in keys:
            address = json_obj['address']
        else:
            address = None
        age = calculate_age(patient_identification)
        patient_gender = get_gender(patient_identification)
        try:
            patient = Patient.objects.filter(identification=patient_identification).first()
            if patient is None:
                patient = Patient(
                    identification=patient_identification,
                    phone_number=phone_number,
                    patient_gender=patient_gender,
                    address=address,
                    patient_name=patient_name,
                    age=age
                )
                patient.save()
                user.patient_set.add(patient)
                return JsonResponse({"result": "1", "message": "添加患者成功！"})
            else:
                patient_1 = user.patient_set.filter(patient_id=patient.patient_id).first()
                if patient_1 is None:
                    user.patient_set.add(patient)
                    return JsonResponse({"result": "1", "message": "添加患者成功！"})
                else:
                    return JsonResponse({"result": "0", "message": "患者已经存在！"})
        except:
            return JsonResponse({"result": "0", "message": "出错啦！"})


class DeletePatient(View):
    @method_decorator(logging_check)
    def delete(self, request):
        json_str = request.body
        json_obj = json.loads(json_str)
        patient_id_list = json_obj['patient_ids']
        try:
            with transaction.atomic():
                for patient_id in patient_id_list:
                    try:
                        patient = Patient.objects.get(patient_id=patient_id)
                        token = request.META.get('HTTP_AUTHORIZATION')
                        jwt_token = jwt.decode(token, settings.JWT_TOKEN_KEY, algorithms='HS256')
                        user_id = User.objects.get(phone_number=jwt_token['username']).user_id
                        user = User.objects.get(user_id=user_id)
                        user.patient_set.remove(patient)
                    except Patient.DoesNotExist:
                        return JsonResponse({"result": "0", "message": f"患者ID {patient_id} 不存在！"})
        except:
            return JsonResponse({"result": "0", "message": "出错啦！"})

        return JsonResponse({"result": "1", "message": "删除患者成功！"})


class UpdatePatient(View):
    @method_decorator(logging_check)
    def put(self, request, patient_id):
        json_str = request.body
        json_obj = json.loads(json_str)
        patient_name = json_obj['patient_name']
        patient_identification = json_obj['patient_identification']
        phone_number = json_obj['phone_number']
        address = json_obj['address']
        try:
            patient = Patient.objects.get(patient_id=patient_id)
            patient.patient_name = patient_name
            patient.identification = patient_identification
            patient.phone_number = phone_number
            patient.address = address
            patient.save()
            return JsonResponse({"result": "1", "message": "更新患者信息成功！"})
        except:
            return JsonResponse({"result": "0", "message": "出错啦！"})


class GetMessage(View):
    @method_decorator(logging_check)
    def get(self, request):
        token = request.META.get('HTTP_AUTHORIZATION')
        jwt_token = jwt.decode(token, settings.JWT_TOKEN_KEY, algorithms='HS256')
        user_id = User.objects.get(phone_number=jwt_token['username']).user_id
        messages = Message.objects.filter(user_id=user_id).order_by('-message_id')
        messages_read = []
        messages_unread = []
        messages_total = []
        for message in messages:
            if message.is_read:
                messages_read.append({"title": message.title,
                                      "content": message.content,
                                      "is_read": message.is_read,
                                      "time": message.message_time.strftime("%Y-%m-%d"),
                                      })
            else:
                messages_unread.append({"title": message.title,
                                        "content": message.content,
                                        "is_read": message.is_read,
                                        "time": message.message_time.strftime("%Y-%m-%d"),
                                        })
            messages_total.append({
                "id": message.message_id, "title": message.title,
                "content": message.content,
                "is_read": message.is_read,
                "time": message.message_time.strftime("%Y-%m-%d"),
            })
        return JsonResponse({"result": "1", "messages_unread": messages_unread, "messages_read": messages_read,
                             "messages": messages_total})


class UnreadMessage(View):
    @method_decorator(logging_check)
    def get(self, request):
        token = request.META.get('HTTP_AUTHORIZATION')
        jwt_token = jwt.decode(token, settings.JWT_TOKEN_KEY, algorithms='HS256')
        user_id = User.objects.get(phone_number=jwt_token['username']).user_id
        messages = Message.objects.filter(user_id=user_id, is_read=False).first()
        if messages:
            return JsonResponse({"result": "1", "unread": True})
        return JsonResponse({"result": "1", "unread": False})


class ReadMessage(View):
    @method_decorator(logging_check)
    def get(self, request, message_id):
        message = Message.objects.get(message_id=message_id)
        message.is_read = True
        message.save()
        try:
            return JsonResponse({"result": "1", "message": "已读"})
        except:
            return JsonResponse({"result": "0", "message": "出错啦！"})


def generate_vacancy_settings():
    tmp = Vacancy_setting.objects.all()
    if tmp:
        return
    for day in range(1, 8):
        for start_time in range(8, 11):
            vacancy_time = Decimal(str(start_time))
            vacancy_setting = Vacancy_setting(
                vacancy_day=day,
                vacancy_time=vacancy_time,
                vacancy_cnt=10
            )
            vacancy_setting.save()
            vacancy_time = Decimal(str(start_time))
            vacancy_setting = Vacancy_setting(
                vacancy_day=day,
                vacancy_time=vacancy_time + Decimal('0.5'),
                vacancy_cnt=10
            )
            vacancy_setting.save()

        for start_time in range(14, 17):
            vacancy_time = Decimal(str(start_time))
            vacancy_setting = Vacancy_setting(
                vacancy_day=day,
                vacancy_time=vacancy_time,
                vacancy_cnt=10
            )
            vacancy_setting.save()
            vacancy_time = Decimal(str(start_time))
            vacancy_setting = Vacancy_setting(
                vacancy_day=day,
                vacancy_time=vacancy_time + Decimal('0.5'),
                vacancy_cnt=10
            )
            vacancy_setting.save()


def generate_vacancy():
    vacancy_exists = Vacancy.objects.exists()
    if vacancy_exists and Vacancy.objects.latest('start_time').start_time > datetime.now():
        start_date_vacancy = Vacancy.objects.latest('start_time')
        start_date = start_date_vacancy.start_time
        end_date = datetime.now() + timedelta(days=7)
    else:
        start_date = datetime.now()
        end_date = datetime.now() + timedelta(days=7)
    delta = end_date - start_date
    for i in range(1, delta.days + 1):
        current_date = start_date + timedelta(days=i)

        # 根据日期查询对应的Schedule
        schedules = Schedule.objects.filter(schedule_day=current_date.weekday() + 1)

        for schedule in schedules:
            if schedule.schedule_is_morning:
                start_time = current_date.replace(hour=8, minute=0, second=0, microsecond=0)
                end_time = current_date.replace(hour=11, minute=0, second=0, microsecond=0)
            else:
                start_time = current_date.replace(hour=14, minute=0, second=0, microsecond=0)
                end_time = current_date.replace(hour=17, minute=0, second=0, microsecond=0)

            current_time = start_time
            while current_time < end_time:
                # 创建相应的Vacancy对象
                vacancy_day = current_time.weekday() + 1
                minutes = 0 if current_time.minute == 0 else 0.5
                vacancy_time = current_time.hour + minutes
                vacancy_setting = Vacancy_setting.objects.filter(vacancy_day=vacancy_day, vacancy_time=vacancy_time). \
                    first()
                if vacancy_setting:
                    vacancy = Vacancy(
                        doctor_id=schedule.doctor_id,
                        start_time=current_time,
                        end_time=current_time + timedelta(minutes=30),
                        vacancy_left=vacancy_setting.vacancy_cnt,
                        vacancy_count=vacancy_setting.vacancy_cnt
                    )
                    vacancy.save()
                current_time += timedelta(minutes=30)


def is_illegal_phoneNumber(phone):
    pattern = re.compile(r'^(13[0-9]|14[0|5|6|7|9]|15[0|1|2|3|5|6|7|8|9]|'
                         r'16[2|5|6|7]|17[0|1|2|3|5|6|7|8]|18[0-9]|'
                         r'19[1|3|5|6|7|8|9])\d{8}$')
    if pattern.search(phone):
        return False
    else:
        return True


def start():
    scheduler = BackgroundScheduler()
    scheduler.add_jobstore(DjangoJobStore(), "default")
    scheduler.add_job(generate_vacancy, 'cron', hour=0, minute=0, coalesce=True)

    scheduler.start()


try:
    generate_vacancy_settings()
    generate_vacancy()
    start()
except django.db.ProgrammingError:
    pass
