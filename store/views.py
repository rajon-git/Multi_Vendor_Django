from django.shortcuts import render,redirect
from .models import Category, Tax, Product, Cart, CartOrder, CartOrderItem, Coupon, Notification
from .serializer import CategorySerializer, ProductSerializer, CartOrderItemSerializer, CartSerializer, CartOrderSerializer, CouponSerializer, NotificationSerializer
from rest_framework import generics,status
from rest_framework.permissions import AllowAny, IsAuthenticated
from userauths.models import User
from decimal import Decimal
from rest_framework.response import Response
from django.db.models import Q
import stripe
from django.conf import settings
import requests
from django.shortcuts import get_object_or_404
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
import os
from dotenv import load_dotenv
load_dotenv()

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
EMAIL_USER = os.getenv("EMAIL_USER")

def send_notification(user=None, vendor=None, order=None, order_item=None):
    Notification.objects.create(
        user = user,
        vendor=vendor,
        order=order,
        order_item=order_item
    )
# Create your views here.
class CategoryListAPIView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]

class ProductListAPIView(generics.ListAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]

class ProductDetailsAPIView(generics.RetrieveAPIView):
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        slug = self.kwargs['slug']
        return Product.objects.get(slug = slug)
    
class CartAPIView(generics.ListCreateAPIView):
    serializer_class = CartSerializer
    queryset = Cart.objects.all()
    permission_classes = (AllowAny,)

    def create(self, request, *args, **kwargs):
        payload = request.data

        product_id = payload['product_id']
        user_id = payload['user_id']
        user_id = payload['user_id']
        qty = payload['qty']
        price = payload['price']
        shipping_amount = payload['shipping_amount']
        country = payload['country']
        size = payload['size']
        color = payload['color']
        cart_id = payload['cart_id']

        product = Product.objects.get(id = product_id)
        if user_id != 'undefined':
            user = User.objects.get(id = user_id)
        else:
            user=None
        tax = Tax.objects.filter(country=country).first()
        if tax:
            tax_rate = tax.rate / 100
        else:
            tax_rate = 0

        cart = Cart.objects.filter(cart_id = cart_id, product = product).first()

        if cart:
            cart.product = product
            cart.user = user
            cart.qty = qty
            cart.price = price
            cart.sub_total = Decimal(price) * Decimal(qty)
            cart.shipping_amount = Decimal(shipping_amount) * Decimal(qty)
            cart.tax_fee = int(qty) * Decimal(tax_rate)
            cart.color = color
            cart.size = size
            cart.country = country
            cart.cart_id = cart_id

            service_fee_perchnatage = 10 / 100
            cart.service_fee = Decimal(service_fee_perchnatage) * cart.sub_total
            cart.total = cart.shipping_amount + cart.sub_total + cart.tax_fee + cart.service_fee
            cart.save()

            return Response({'message': 'Cart Updated Successfully'}, status=status.HTTP_200_OK)
        else:
            cart = Cart()
            cart.product = product
            cart.user = user
            cart.qty = qty
            cart.price = price
            cart.sub_total = Decimal(price) * Decimal(qty)
            cart.shipping_amount = Decimal(shipping_amount) * Decimal(qty)
            cart.tax_fee = int(qty) * Decimal(tax_rate)
            cart.color = color
            cart.size = size
            cart.country = country
            cart.cart_id = cart_id

            service_fee_perchnatage = 10 / 100
            cart.service_fee = Decimal(service_fee_perchnatage) * cart.sub_total
            cart.total = cart.shipping_amount + cart.sub_total + cart.tax_fee + cart.service_fee
            cart.save()

            return Response({'message': 'Cart Created Successfully'}, status=status.HTTP_201_CREATED)


class CartListView(generics.ListAPIView):
    serializer_class = CartSerializer
    permission_classes = (AllowAny,)

    def get_queryset(self):
        cart_id = self.kwargs['cart_id']
        user_id = self.kwargs.get('user_id') 
        if user_id is not None:
            user = User.objects.get(id=user_id)
            queryset = Cart.objects.filter(Q(user=user, cart_id=cart_id) | Q(user=user))
        else:
            queryset = Cart.objects.filter(cart_id=cart_id)
        
        return queryset
    
class CartDetailView(generics.RetrieveAPIView):
    serializer_class = CartSerializer
    permission_classes = [AllowAny,]
    lookup_field = "cart_id"

    def get_queryset(self):
        cart_id = self.kwargs['cart_id']
        user_id = self.kwargs.get('user_id') 
        if user_id is not None:
            user = User.objects.get(id=user_id)
            queryset = Cart.objects.filter(Q(user=user, cart_id=cart_id) | Q(user=user))
        else:
            queryset = Cart.objects.filter(cart_id=cart_id)
        return queryset
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        total_shipping = 0.0
        total_tax = 0.0
        total_service_fee = 0.0
        total_sub_total = 0.0
        total_total = 0.0

        for cart_item in queryset:
            total_shipping += float(self.calculate_shipping(cart_item))
            total_tax += float(self.calculate_tax(cart_item))
            total_service_fee += float(self.calculate_service_fee(cart_item))
            total_sub_total += float(self.calculate_sub_total(cart_item))
            total_total += float(self.calculate_total(cart_item))
        
        data = {
            'shipping': total_shipping,
            'tax': total_tax,
            'service_fee': total_service_fee,
            'sub_total': total_sub_total,
            'total': total_total,
        }
        return Response(data)
    def calculate_shipping(self, cart_item):
        return cart_item.shipping_amount
    def calculate_tax(self, cart_item):
        return cart_item.tax_fee
    def calculate_service_fee(self, cart_item):
        return cart_item.service_fee
    def calculate_sub_total(self, cart_item):
        return cart_item.sub_total
    def calculate_total(self, cart_item):
        return cart_item.total
    
class CartItemDeleteAPIView(generics.DestroyAPIView):
    serializer_class = CartSerializer
    lookup_field ='cart_id'

    def get_object(self):
        cart_id = self.kwargs['cart_id']
        item_id = self.kwargs['item_id']
        user_id = self.kwargs.get('user_id')

        if user_id is not None:
            user = User.objects.get(id=user_id)
            cart = Cart.objects.get(id=item_id, cart_id=cart_id, user=user)
        else:
            cart = Cart.objects.get(id=item_id, cart_id=cart_id)

        return cart
    
class CreateOrderAPIView(generics.CreateAPIView):
    serializer_class = CartOrderSerializer
    queryset = CartOrder.objects.all()
    permission_classes = (AllowAny,)

    def create(self, request):
        payload = request.data

        full_name = payload['full_name']
        email = payload['email']
        mobile = payload['mobile']
        address = payload['address']
        city = payload['city']
        state = payload['state']
        country = payload['country']
        cart_id = payload['cart_id']
        user_id = payload['user_id']

        # if user_id != 0:
        #     user = User.objects.get(id=user_id)
        # else:
        #     user = None

        try:
            user = User.objects.get(id=user_id)
        except:
            user = None

        cart_items = Cart.objects.filter(cart_id=cart_id)

        total_shipping = Decimal(0.00)
        total_tax = Decimal(0.00)
        total_service_fee = Decimal(0.00)
        total_sub_total = Decimal(0.00)
        total_initial_total = Decimal(0.00)
        total_total = Decimal(0.00)

        order = CartOrder.objects.create(
            full_name=full_name,
            email=email,
            mobile=mobile,
            address=address,
            city=city,
            state=state,
            country=country,
        )

        for c in cart_items:
            CartOrderItem.objects.create(
                order=order,
                product = c.product,
                vendor = c.product.vendor,
                qty=c.qty,
                price=c.price,
                sub_total=c.sub_total,
                shipping_amount=c.shipping_amount,
                tax_fee=c.tax_fee,
                service_fee=c.service_fee,
                color=c.color,
                size=c.size,
                initial_total=c.total,
                total = c.total
            )

            total_shipping += Decimal(c.shipping_amount)
            total_tax += Decimal(c.tax_fee)
            total_service_fee += Decimal(c.service_fee)
            total_sub_total += Decimal(c.sub_total)
            total_initial_total += Decimal(c.total)
            total_total += Decimal(c.total)

            order.vendor.add(c.product.vendor)

        order.sub_total = total_sub_total
        order.shipping_amount = total_shipping
        order.tax_fee = total_tax
        order.service_fee = total_service_fee
        order.initial_total = total_initial_total
        order.total = total_total

        order.save()
        return Response({'message': 'Order Created Successfully', 'order_oid':order.oid}, status=status.HTTP_201_CREATED)

class CheckoutAPIView(generics.RetrieveAPIView):
    serializer_class = CartOrderSerializer
    lookup_field = "order_oid"

    def get_object(self):
        order_oid = self.kwargs['order_oid']
        order = CartOrder.objects.get(oid=order_oid)
        return order
    
class CouponAPIView(generics.CreateAPIView):
    serializer_class = CouponSerializer
    queryset = Coupon.objects.all()
    permission_classes = (AllowAny,)

    def create(self, request):
        payload = request.data

        order_oid = payload['order_oid']
        coupon_code = payload['coupon_code']

        order = CartOrder.objects.get(oid=order_oid)
        coupon = Coupon.objects.filter(code=coupon_code).first()

        if coupon:
            order_items = CartOrderItem.objects.filter(order=order, vendor=coupon.vendor)
            if order_items:
                for i in order_items:
                    if not coupon in  i.coupon.all():
                        discount = coupon.discount
                        ddiscount = coupon.discount
                        print('disocunt====', discount)
                        print('ddiscount ====', discount)
                        i.total -= discount
                        i.sub_total -= discount
                        i.coupon.add(coupon)
                        i.saved += discount

                        order.total -= discount
                        order.sub_total -= discount
                        order.saved += discount

                        i.save()
                        order.save()
                        return Response({"message":"Coupon Activated", "icon":"success"}, status=status.HTTP_200_OK)
                    else:
                        return Response({"message":"Coupon Already Activated", "icon":"warning"}, status=status.HTTP_200_OK)
            else:
                return Response({"message":"Order Item Doesn't Exists", "icon":"error"}, status=status.HTTP_200_OK)
        else:
            return Response({"message":"Coupon Does Not Exists", "icon":"error"}, status=status.HTTP_200_OK)

class StripeCheckoutView(generics.CreateAPIView):
    serializer_class = CartOrderSerializer
    permission_classes = [AllowAny]
    queryset = CartOrder.objects.all()

    def create(self, *args, **kwargs):
        order_oid = self.kwargs['order_oid']
        order = CartOrder.objects.get(oid=order_oid)

        if not order:
            return Response({"message": "Order not found", "icon": "error"}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            checkout_session = stripe.checkout.Session.create(
                customer_email = order.email,
                payment_method_types = ['card'],
                line_items = [
                    {
                        'price_data': {
                            'currency': 'usd',
                            'product_data': {
                                'name': order.full_name,
                            },
                            'unit_amount': int(order.total * 100),
                        },
                        'quantity': 1,
                    }
                ],
                mode = 'payment',
                success_url = 'http://localhost:5173/payment-success/' + order_oid +'?session_id={CHECKOUT_SESSION_ID}',
                cancel_url = 'http://localhost:5173/payment-cancel/?session_id={CHECKOUT_SESSION_ID}',
            )

            order.stripe_Session_id = checkout_session.id
            order.save()

            return redirect(checkout_session.url)
        except stripe.error.StripeError as e:
            return Response({"error": f"Error processing payment: {str(e)}", "icon": "error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class PaymentSuccessView(generics.CreateAPIView):
    serializer_class = CartOrderSerializer
    queryset = CartOrder.objects.all()

    def create(self, request, *args, **kwargs):
        payload = request.data
        order_oid = payload.get('order_oid')
        session_id = payload.get('session_id')

        if not order_oid or not session_id:
            return Response({'error': 'Missing order_oid or session_id'}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch the order
        order = get_object_or_404(CartOrder, oid=order_oid)
        order_items = CartOrderItem.objects.filter(order=order)

        if session_id and session_id != "null":
            try:
                session = stripe.checkout.Session.retrieve(session_id)
            except Exception as e:
                return Response({"error": "Failed to retrieve Stripe session."}, status=status.HTTP_400_BAD_REQUEST)

            payment_status = session.get("payment_status", "").lower()

            if payment_status == "paid":
                if order.payment_status == "pending":
                    # Mark the order as paid
                    order.payment_status = "paid"
                    order.save()

                    # Send customer confirmation email
                    self.send_customer_email(order, order_items)

                    # Notify buyer
                    if order.buyer:
                        send_notification(user=order.buyer, order=order)

                    # Notify vendors and send sale email
                    for item in order_items:
                        send_notification(vendor=item.vendor, order=order, order_item=item)
                        self.send_vendor_email(item.vendor, order, order_items)

                    return Response({"message": "Payment Successful"}, status=status.HTTP_201_CREATED)
                else:
                    return Response({"message": "Already Paid"}, status=status.HTTP_200_OK)

            elif payment_status == "unpaid":
                return Response({"message": "Your Invoice is unpaid"}, status=status.HTTP_200_OK)

            elif payment_status == "canceled":
                return Response({"message": "Your Invoice is Cancelled"}, status=status.HTTP_200_OK)

            else:
                return Response({"message": "An error occurred, please try again."}, status=status.HTTP_400_BAD_REQUEST)

        else:
            return Response({"error": "Invalid session ID."}, status=status.HTTP_400_BAD_REQUEST)

    def send_customer_email(self, order, order_items):
        """Send order confirmation email to customer."""
        context = {'order': order, 'order_items': order_items}
        subject = "Order Placed Successfully"
        text_body = render_to_string("email/customer_order_confirmation.txt", context)
        html_body = render_to_string("email/customer_order_confirmation.html", context)

        msg = EmailMultiAlternatives(
            subject=subject,
            from_email=os.getenv('EMAIL_HOST_USER'),
            to=[order.email],
            body=text_body
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send()

    def send_vendor_email(self, vendor, order, order_items):
        """Send new sale email to vendor."""
        context = {'order': order, 'order_items': order_items}
        subject = "New Sale!"
        text_body = render_to_string("email/vendor_order_sale.txt", context)
        html_body = render_to_string("email/vendor_order_sale.html", context)

        msg = EmailMultiAlternatives(
            subject=subject,
            from_email=os.getenv('EMAIL_HOST_USER'),
            to=[vendor.user.email],
            body=text_body
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send()